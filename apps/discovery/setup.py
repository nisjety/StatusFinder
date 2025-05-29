from setuptools import setup, find_packages

setup(
    name="discovery",
    version="1.0.0",
    packages=find_packages(include=['discovery', 'discovery.*']),
    python_requires=">=3.8",
    install_requires=[
        'scrapy>=2.6.0',
        'playwright>=1.30.0',
        'pymongo>=4.3.0',
        'redis>=4.5.0',
        'pika>=1.3.0',
        'scrapyd>=1.3.0',
        'pyOpenSSL>=23.0.0',
        'service_identity>=21.1.0',
        'pillow>=9.3.0'
    ],
    entry_points={
        'scrapy': ['settings = discovery.settings'],
        'scrapy.project': ['discovery = discovery']
    },
    package_data={
        'discovery': ['*.json', '*.conf', '*.txt'],
    },
    zip_safe=False,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Framework :: Scrapy',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Software Development :: Libraries :: Application Frameworks',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    description='A modular Scrapy project for web crawling tasks',
    author='Your Name',
    author_email='your.email@example.com',
    url='https://github.com/yourusername/discovery'
)