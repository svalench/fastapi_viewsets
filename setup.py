from setuptools import setup
from pathlib import Path

this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

setup(
    name='fastapi_viewsets',
    author='Alexander Valenchits',
    version='0.1.3',
    description="""Package for creating endpoint
     controller classes for models in the database""",
    url='http://example.com',
    install_requires=['fastapi>=0.76.0', 'uvicorn>=0.17.6', 'SQLAlchemy>=1.4.36'],
    packages=['fastapi_viewsets'],
    classifiers=[
        "Programming Language :: Python :: 3.9",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    long_description=long_description,
    long_description_content_type='text/markdown'
)
