""" Register on PyPI """
from setuptools import setup


setup(
    name='simpleavs',
    packages=['simpleavs'],
    version='0.3',
    description='Simple AVS API Client (Amazon Alexa Voice Service) for v20160207',
    author='Rob Ladbrook',
    author_email='simpleavs@slyfx.com',
    url='https://github.com/robladbrook/simpleavs',
    download_url='https://github.com/robladbrook/simpleavs/tarball/0.3',
    keywords=['avs', 'alexa', 'amazon', 'voice'],
    classifiers=[],
    install_requires=['pyyaml', 'requests', 'hyper']
)
