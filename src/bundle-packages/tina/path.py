from .common import *
from .advans import *
import ezprof


EPS = 1e-6
INF = 1e6


@ti.func
def sphere_intersect(s_id, s_pos, s_rad, r_org, r_dir):
    i_t = INF
    op = s_pos - r_org
    b = op.dot(r_dir)
    det = b**2 - op.norm_sqr() + s_rad**2
    if det >= 0:
        det = ti.sqrt(det)
        i_t = b - det
        if i_t <= EPS:
            i_t = b + det
            if i_t <= EPS:
                i_t = INF
    i_pos = r_org + i_t * r_dir
    i_nrm = (i_pos - s_pos).normalized()
    i_tex = V(0., 0.)  # NotImplemented
    return i_t, s_id, i_pos, i_nrm, i_tex


@ti.func
def triangle_intersect(id, v0, v1, v2, ro, rd):
    e1 = v1 - v0
    e2 = v2 - v0
    p = rd.cross(e2)
    det = e1.dot(p)
    r = ro - v0

    t, u, v = INF, 0.0, 0.0
    ipos, inrm, itex = V(0.0, 0.0, 0.0), V(0.0, 0.0, 0.0), V(0.0, 0.0)

    if det < 0:
        r = -r
        det = -det

    if det >= EPS:
        u = r.dot(p)
        if 0 <= u <= det:
            q = r.cross(e1)
            v = rd.dot(q)
            if v >= 0 and u + v <= det:
                t = e2.dot(q)
                det = 1 / det
                t *= det
                u *= det
                v *= det
                inrm = e1.cross(e2).normalized()
                ipos = ro + t * rd
                itex = V(u, v)

    return t, id, ipos, inrm, itex


@ti.func
def make_null_intersect():
    ret = [INF, 0, V(0., 0., 0.), V(0., 0., 0.), V(0., 0.)]
    return ret


@ti.func
def union_intersect(ret: ti.template(), ret2):
    if ret2[0] < ret[0]:
        for x, y in ti.static(zip(ret, ret2)):
            x.assign(y)


@ti.data_oriented
class BRDF:
    def __init__(self, **kwargs):
        @ti.materialize_callback
        def _():
            for k, v in kwargs.items():
                getattr(self, k)[None] = v

    def brdf(self, idir, odir):
        raise NotImplementedError

    @ti.func
    def rand_odir(self, idir):
        return 1, spherical(ti.random(), ti.random())

    @ti.func
    def bounce(self, dir, nrm):
        axes = tangentspace(nrm)
        idir = axes.transpose() @ -dir
        fac, odir = self.rand_odir(idir)
        clr = self.brdf(idir, odir)
        return axes @ odir, clr * fac


class CookTorranceBRDF(BRDF):
    def __init__(self, **kwargs):
        self.roughness = ti.field(float, ())
        self.metallic = ti.field(float, ())
        self.specular = ti.field(float, ())
        self.basecolor = ti.Vector.field(3, float, ())

        super().__init__(**kwargs)

    @ti.func
    def ischlick(self, cost):
        k = (self.roughness[None] + 1)**2 / 8
        return k + (1 - k) * cost

    @ti.func
    def fresnel(self, f0, HoV):
        return f0 + (1 - f0) * (1 - HoV)**5

    @ti.func
    def brdf(self, idir, odir):
        roughness = self.roughness[None]
        metallic = self.metallic[None]
        specular = self.specular[None]
        basecolor = self.basecolor[None]
        half = (idir + odir).normalized()
        NoH = max(EPS, half.z)
        NoL = max(EPS, idir.z)
        NoV = max(EPS, odir.z)
        HoV = min(1 - EPS, max(EPS, half.dot(odir)))
        ndf = roughness**2 / (NoH**2 * (roughness**2 - 1) + 1)**2
        vdf = 0.25 / (self.ischlick(NoL) * self.ischlick(NoV))
        f0 = metallic * basecolor + (1 - metallic) * 0.16 * specular**2
        ks, kd = f0, (1 - f0) * (1 - metallic)
        fdf = self.fresnel(f0, NoV)
        return kd * basecolor + ks * fdf * vdf * ndf / ti.pi


class DiffuseBRDF(BRDF):
    def __init__(self, **kwargs):
        self.color = ti.Vector.field(3, float, ())

        super().__init__(**kwargs)

    @ti.func
    def brdf(self, idir, odir):
        return self.color[None]


class SpecularBRDF(BRDF):
    def __init__(self, **kwargs):
        self.color = ti.Vector.field(3, float, ())

        super().__init__(**kwargs)

    @ti.func
    def rand_odir(self, idir):
        odir = reflect(-idir, V(0., 0., 1.))
        return odir

    @ti.func
    def brdf(self, idir, odir):
        return self.color[None]


class BlinnPhongBRDF(BRDF):
    def __init__(self, **kwargs):
        self.shineness = ti.field(float, ())

        super().__init__(**kwargs)

    @ti.func
    def brdf(self, idir, odir):
        shineness = self.shineness[None]
        half = (odir + idir).normalized()
        return (shineness + 8) / 8 * pow(max(0, half.z), shineness)


@ti.data_oriented
class PathEngine:
    def __init__(self, res=512, nrays=1, ntimes=1, nsteps=1, maxfaces=1024):
        self.res = tovector(res if hasattr(res, '__getitem__') else (res, res))
        self.nrays = V(self.res.x, self.res.y, nrays)
        self.ntimes = ntimes
        self.nsteps = nsteps

        self.count = ti.field(int, self.res)
        self.screen = ti.Vector.field(3, float, self.res)
        self.ray_org = ti.Vector.field(3, float, self.nrays)
        self.ray_dir = ti.Vector.field(3, float, self.nrays)
        self.ray_color = ti.Vector.field(3, float, self.nrays)

        self.maxfaces = maxfaces
        self.tri_count = ti.field(int, ())
        self.tri_v0 = ti.Vector.field(3, float, self.maxfaces)
        self.tri_v1 = ti.Vector.field(3, float, self.maxfaces)
        self.tri_v2 = ti.Vector.field(3, float, self.maxfaces)
        self.tri_id = ti.field(int, self.maxfaces)

        @ti.materialize_callback
        def _():
            from .util.assimp import readobj, objmtlids
            obj = readobj('/home/bate/Develop/three_taichi/assets/sphere.obj')
            verts = obj['v'][obj['f'][:, :, 0]]
            mids = objmtlids(obj)

            assert len(mids) == len(verts)
            assert len(verts) < maxfaces, len(verts)
            self.set_triangles(verts, mids)

    @ti.kernel
    def set_triangles(self, verts: ti.ext_arr(), mids: ti.ext_arr()):
        self.tri_count[None] = min(verts.shape[0], self.maxfaces)
        for i in range(self.tri_count[None]):
            self.tri_id[i] = mids[i]
            for k in ti.static(range(3)):
                out = ti.static([self.tri_v0, self.tri_v1, self.tri_v2][k])
                for l in ti.static(range(3)):
                    out[i][l] = verts[i, k, l]

    @ti.func
    def generate_ray(self, I):
        coor = I / self.res * 2 - 1
        org = V(0., 0., -2.)
        dir = V23(coor, 1.).normalized()
        return org, dir

    @ti.kernel
    def generate_rays(self):
        for r in ti.grouped(self.ray_org):
            I = r.xy + V(ti.random(), ti.random())
            org, dir = self.generate_ray(I)
            self.ray_org[r] = org
            self.ray_dir[r] = dir
            self.ray_color[r] = V(1., 1., 1.)

    @ti.func
    def intersect(self, org, dir):
        ret = make_null_intersect()
        for i in range(self.tri_count[None]):
            id = self.tri_id[i]
            v0, v1, v2 = self.tri_v0[i], self.tri_v1[i], self.tri_v2[i]
            tmp = triangle_intersect(id, v0, v1, v2, org, dir)
            union_intersect(ret, tmp)
        return ret

    @ti.func
    def bounce_ray(self, org, dir, i_id, i_pos, i_nrm, i_tex):
        org = i_pos + i_nrm * EPS
        color = V(0., 0., 0.)
        if i_id == 0:
            dir *= 0
            color = V(1., 0., 1.)
        return color, org, dir

    @ti.kernel
    def step_rays(self):
        for r in ti.grouped(self.ray_org):
            if all(self.ray_dir[r] == 0):
                continue

            org = self.ray_org[r]
            dir = self.ray_dir[r]
            t, i_id, i_pos, i_nrm, i_tex = self.intersect(org, dir)
            if t >= INF:
                self.ray_color[r] *= 0
                self.ray_dir[r] *= 0
            else:
                color, org, dir = self.bounce_ray(org, dir, i_id, i_pos, i_nrm, i_tex)
                self.ray_color[r] *= color
                self.ray_org[r] = org
                self.ray_dir[r] = dir

    @ti.kernel
    def update_screen(self):
        for I in ti.grouped(self.screen):
            for samp in range(self.nrays.z):
                r = V23(I, samp)
                color = self.ray_color[r]
                count = self.count[I]
                self.screen[I] *= count / (count + 1)
                self.screen[I] += color / (count + 1)
                self.count[I] += 1

    def main(self):
        for i in range(self.ntimes):
            with ezprof.scope('gen'):
                self.generate_rays()
            for j in range(self.nsteps):
                with ezprof.scope('step'):
                    self.step_rays()
            with ezprof.scope('update'):
                self.update_screen()
        with ezprof.scope('export'):
            img = self.screen.to_numpy()

        img = aces_tonemap(ti.imresize(img, 512))
        ezprof.show()
        ti.imshow(img)


if __name__ == '__main__':
    ti.init(ti.cpu)
    engine = PathEngine()
    engine.main()
