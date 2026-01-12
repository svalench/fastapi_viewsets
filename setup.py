from setuptools import setup
from pathlib import Path

this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

setup(
    name='fastapi_viewsets',
    author='Alexander Valenchits',
    version='1.1.0',
    description="""Package for creating endpoint
     controller classes for models in the database""",
    url='https://github.com/svalench/fastapi_viewsets',
    install_requires=[
        'fastapi>=0.76.0',
        'uvicorn>=0.17.6',
        'SQLAlchemy>=1.4.36',
        'python-dotenv>=0.19.0',
        'typing-extensions>=4.0.0; python_version<"3.8"'
    ],
    extras_require={
        'sqlalchemy': [
            'SQLAlchemy>=1.4.36',
        ],
        'tortoise': [
            'tortoise-orm>=0.20.0',
            'asyncpg>=0.28.0',
        ],
        'peewee': [
            'peewee>=3.17.0',
        ],
        'test': [
            'pytest>=7.0.0',
            'pytest-asyncio>=0.21.0',
            'pytest-cov>=4.0.0',
            'httpx>=0.24.0',
            'faker>=18.0.0',
            'aiosqlite>=0.19.0',
        ]
    },
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
