from setuptools import setup, find_packages


def readme():
    with open('README.md') as f:
        return f.read()


name = 'http2py'
version = '0.1.0'
setup(
    name=f'{name}',
    version=f'{version}',
    description='Tools to create python binders to http web services.',
    long_description=readme(),
    long_description_content_type="text/markdown",
    url=f'https://github.com/i2mint/{name}',
    author='Thor Whalen',
    license='Apache',
    packages=find_packages(),
    install_requires=[
        'glom==20.8.0',
        'i2==0.0.6',
        'requests==2.24.0',
        'argh==0.26.2',
        'PyYAML==5.3.1'
    ],
    include_package_data=True,
    zip_safe=False,
    # download_url='https://github.com/i2mint/{name}/archive/v{version}.zip',
    keywords=['webservice', 'http', 'requests', 'API'],
    classifiers=[
        'Development Status :: 3 - Alpha',
        # Either
        # "3 - Alpha",
        # "4 - Beta" or
        # "5 - Production/Stable" as the current state.

        'Intended Audience :: Developers',
        'Topic :: Software Development',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python :: 3.7',
    ],
)
