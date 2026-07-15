from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="qilin-os-agent",
    version="1.0.0",
    author="chuanchuan123321",
    author_email="2774421277@qq.com",
    description="麒麟OS-Agent - 智能操作系统助手 for executing system commands, file operations, web search and more",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/chuanchuan123321/qilin-os-agent",
    packages=find_packages(),
    py_modules=["chat"],
    include_package_data=True,
    package_data={
        "agent": [
            "core/prompt/*.txt",
            "skills/*/SKILL.md",
            "ui/desktop/*.html",
            "ui/desktop/*.css",
            "ui/desktop/*.js",
            "ui/desktop/assets/*",
            "ui/desktop/vendor/katex/*",
            "ui/desktop/vendor/katex/fonts/*",
        ]
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.11",
    install_requires=[
        "requests>=2.28.0",
        "python-dotenv>=0.20.0",
        "rich>=13.0.0",
        "beautifulsoup4>=4.11.0",
        "chardet>=5.0.0",
        "lark-oapi>=1.5.0",
        "nest_asyncio>=1.5.0",
        "certifi>=2023.0.0",
        "reportlab>=4.0.0",
        "markdown>=3.4.0",
        "fpdf2>=2.7.0",
        "eel>=0.14.0",
        "PyPDF2>=3.0.0",
        "python-docx>=1.1.0",
        "openpyxl>=3.1.0",
        "langchain==1.2.7",
        "langchain-openai==1.1.7",
        "langgraph==1.0.7",
        "langgraph-checkpoint-sqlite==3.1.0",
    ],
    entry_points={
        "console_scripts": [
            "os-agent=chat:main",
        ],
    },
    keywords="ai automation agent task execution",
    project_urls={
        "Bug Reports": "https://github.com/chuanchuan123321/qilin-os-agent/issues",
        "Source": "https://github.com/chuanchuan123321/qilin-os-agent",
    },
)
