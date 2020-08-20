project_name = 'reblend'
from taichi_glsl.version import version, taichi_version
version = '0.0.1'
taichi_version = '0.6.27'
description = 'Taichi Blender intergration for creating physic-based animations'
long_description = '''
Reblend
=======

Taichi Blender intergration for creating physic-based animations.
'''
classifiers = [
    'Intended Audience :: Developers',
    'Intended Audience :: Science/Research',
    'Topic :: Multimedia :: Graphics',
    'Topic :: Games/Entertainment :: Simulation',
    'Operating System :: OS Independent',
]
python_requires = '>=3.6'
install_requires = [
    'taichi>=' + taichi_version,
]

import setuptools

setuptools.setup(
    name=project_name,
    version=version,
    author='彭于斌',
    author_email='1931127624@qq.com',
    description=description,
    long_description=long_description,
    classifiers=classifiers,
    python_requires=python_requires,
    install_requires=install_requires,
    packages=setuptools.find_packages(),
)
