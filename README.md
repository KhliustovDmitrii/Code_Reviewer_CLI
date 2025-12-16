# Code Review AI Assistant

A command-line tool that automatically reviews your code using the DeepSeek AI API. It analyzes your project structure, reads your source files, and provides intelligent feedback on code quality, potential issues, and improvements.

## Prerequisites

    Python 3.8 or higher

    DeepSeek API key (get one at DeepSeek Platform)

## Installation

    1. Clone or download the project

        git clone git@github.com:KhliustovDmitrii/Code_Reviewer_CLI.git
        cd Code_Reviewer_CLI

    2. Set up virtual environment

        python -m venv venv
        source venv/bin/activate  # On Windows: venv\Scripts\activate

    3. Install dependencies

        pip install -r requirements.txt

    4. Set up your API key

        export DEEPSEEK_API_KEY="your-api-key-here"
     
## Basic Usage

    Review a single file:

        python code_review_tool.py -f main.py

    Review a directory:

        python code_review_tool.py -d src/

    Review recursively with language filter:

        python code_review_tool.py -d . -r -L python -i .gitignore


## Complete Usage Guide

    ### Command Line Options

    | Option	| Description	| Example |
    | -f FILE	| Review a single file	| -f main.py |
    | -d DIRECTORY	| Review all files in a directory |	-d src/ |
    | -r	| Recursive review (with -d)	| -d . -r |
    | -L LANGUAGE	| Filter by programming language	| -L python |
    | -i FILE	| Use ignore patterns file	| -i .gitignore |

    ### Ignore patterns file

    Ignore compiled files
    *.pyc
    __pycache__/
    *.o
    *.so

    Ignore documentation
    docs/
    *.md

    Ignore specific files
    secrets.py
    config.local.json


## The Review Process

    File Collection: Scans specified files/directories, applying ignore patterns

    Structure Analysis: Builds a visual directory tree showing project organization

    Content Processing: Reads and sanitizes file contents for API compatibility

    AI Analysis: Sends project structure and code to DeepSeek API

    Results Display: Presents formatted review with actionable recommendations