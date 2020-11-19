bl_info = {
        'name': 'Taichi Blend',
        'description': 'Taichi Blender intergration',
        'author': 'Taichi Developers',
        'version': (0, 0, 4),
        'blender': (2, 81, 0),
        'location': 'Scripting module',
        'support': 'COMMUNITY',
        'wiki_url': 'https://github.com/taichi-dev/taichi_blend/wiki',
        'tracker_url': 'https://github.com/taichi-dev/taichi_blend/issues',
        'category': 'Physics',
}

from . import package_bundle, render_engine, node_system

modules = [
    package_bundle,
    render_engine,
    node_system,
]

def register():
    for module in modules:
        module.register()


def unregister():
    for module in reversed(modules):
        module.unregister()