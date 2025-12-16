#!/usr/bin/env python3
"""
Automatic Code Review Tool

A simple CLI tool that reviews code using the DeepSeek API.
Usage:
    python code_review_tool.py -f main.py
    python code_review_tool.py -d src -r -L python -i .gitignore
"""

import os
import sys
import re
import argparse
import json
from pathlib import Path
from typing import List, Set, Generator, Optional
import requests


class CodeReviewer:
    """Main class handling the code review process."""
    
    def __init__(self):
        self.api_key = self._get_api_key()
        self.system_prompt = self._load_system_prompt()
    
    def _get_api_key(self) -> str:
        """Get API key from environment variable."""
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            print("Error: DEEPSEEK_API_KEY environment variable not set", file=sys.stderr)
            print("Export it with: export DEEPSEEK_API_KEY='your-key'", file=sys.stderr)
            sys.exit(1)
        return api_key
    
    def _load_system_prompt(self) -> str:
        """Load system prompt from file."""
        script_dir = Path(__file__).parent
        prompt_file = script_dir / "system_prompt.txt"
        
        if not prompt_file.exists():
            print(f"Warning: system_prompt.txt not found in {script_dir}", file=sys.stderr)
            print("Using default system prompt.", file=sys.stderr)
            return """You are an expert code reviewer. Analyze the provided code structure and files.
Provide specific, actionable feedback on code quality, potential bugs, security issues,
and improvements. Focus on practical recommendations."""
        
        try:
            return prompt_file.read_text(encoding="utf-8").strip()
        except Exception as e:
            print(f"Error reading system_prompt.txt: {e}", file=sys.stderr)
            sys.exit(1)
    
    def _should_ignore(self, file_path: Path, ignore_patterns: Set[str]) -> bool:
        """Check if a file should be ignored based on patterns."""
        # Always ignore hidden files and common directories
        if file_path.name.startswith('.'):
            return True
        
        # Check ignore patterns
        for pattern in ignore_patterns:
            pattern = pattern.strip()
            if not pattern or pattern.startswith('#'):
                continue
            
            # Convert simple glob patterns to regex
            if '*' in pattern or '?' in pattern:
                regex_pattern = re.escape(pattern)
                regex_pattern = regex_pattern.replace(r'\*', '.*').replace(r'\?', '.')
                if re.match(f"^{regex_pattern}$", file_path.name):
                    return True
            elif file_path.name == pattern:
                return True
        
        return False
    
    def _load_ignore_patterns(self, ignore_file: Optional[str]) -> Set[str]:
        """Load ignore patterns from file."""
        ignore_patterns = set()
        
        if not ignore_file:
            return ignore_patterns
        
        try:
            with open(ignore_file, 'r', encoding='utf-8') as f:
                ignore_patterns = {line.strip() for line in f if line.strip()}
        except FileNotFoundError:
            print(f"Warning: Ignore file '{ignore_file}' not found", file=sys.stderr)
        except Exception as e:
            print(f"Warning: Error reading ignore file: {e}", file=sys.stderr)
        
        return ignore_patterns
    
    def _collect_files(
        self,
        path: Path,
        recursive: bool = False,
        ignore_patterns: Optional[Set[str]] = None,
        language_filter: Optional[str] = None
    ) -> Generator[Path, None, None]:
        """Collect files for review."""
        if ignore_patterns is None:
            ignore_patterns = set()
        
        if path.is_file():
            if not self._should_ignore(path, ignore_patterns):
                yield path
            return
        
        # Handle directory
        try:
            for item in path.iterdir():
                if self._should_ignore(item, ignore_patterns):
                    continue
                
                if item.is_file():
                    if language_filter:
                        # Simple language filtering by extension
                        extensions = {
                            'python': ['.py'],
                            'javascript': ['.js', '.jsx', '.ts', '.tsx'],
                            'java': ['.java'],
                            'cpp': ['.cpp', '.cc', '.cxx', '.hpp', '.hh', '.h'],
                            'c': ['.c', '.h'],
                            'go': ['.go'],
                            'rust': ['.rs'],
                            'ruby': ['.rb'],
                            'php': ['.php'],
                            'html': ['.html', '.htm'],
                            'css': ['.css'],
                            'markdown': ['.md', '.markdown'],
                        }
                        
                        if language_filter.lower() in extensions:
                            if item.suffix.lower() not in extensions[language_filter.lower()]:
                                continue
                    
                    yield item
                elif item.is_dir() and recursive:
                    yield from self._collect_files(item, recursive, ignore_patterns, language_filter)
        except PermissionError:
            print(f"Warning: No permission to access {path}", file=sys.stderr)
    
    def _build_directory_layout(self, root_path: Path, files: List[Path]) -> str:
        """Build hierarchical directory layout string."""
        if not files:
            return "Directory layout: No files found.\n\n"
        
        # Create a tree structure
        tree = {}
        
        for file_path in sorted(files):
            rel_path = file_path.relative_to(root_path)
            parts = rel_path.parts
            
            # Navigate/construct the tree
            current = tree
            for part in parts[:-1]:  # All but the last part (filename)
                if part not in current:
                    current[part] = {}
                current = current[part]
            
            # Mark the last part as a file
            filename = parts[-1]
            if parts[-1] not in current:
                current[filename] = None  # None indicates a file (leaf node)
    
        def build_tree_lines(node, prefix="", is_last=True, depth=0):
            """Recursively build tree lines."""
            lines = []
            
            if not node:
                return lines
            
            # Sort: directories first, then files
            items = sorted(node.items(), key=lambda x: (x[1] is not None, x[0]))
            
            for i, (name, subtree) in enumerate(items):
                is_last_item = i == len(items) - 1
                
                # Determine connector
                if depth == 0:
                    connector = ""
                else:
                    connector = "└── " if is_last else "├── "
                
                # Build the line
                line = prefix + connector + name
                
                if subtree is None:  # It's a file
                    lines.append(line)
                else:  # It's a directory
                    lines.append(line + "/")
                    # Determine next prefix
                    if depth == 0:
                        next_prefix = ""
                    else:
                        next_prefix = prefix + ("    " if is_last else "│   ")
                    
                    # Recursively add subtree
                    lines.extend(build_tree_lines(
                        subtree, 
                        next_prefix, 
                        is_last_item,
                        depth + 1
                    ))
            
            return lines
        
        # Build the tree lines
        lines = [f"{root_path.name}/"] + build_tree_lines(tree)
        return "\n".join(lines) + "\n\n"
    
    def _read_file_safely(self, file_path: Path) -> Optional[str]:
        """Read file content safely with proper encoding handling."""
        try:
            return file_path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            try:
                # Try other common encodings
                return file_path.read_text(encoding='latin-1')
            except:
                print(f"Warning: Could not read {file_path} (binary file?)", file=sys.stderr)
                return None
        except Exception as e:
            print(f"Warning: Error reading {file_path}: {e}", file=sys.stderr)
            return None
    
    def _build_prompt(self, root_path: Path, files: List[Path]) -> str:
        """Build the complete prompt for API."""
        # Build directory layout
        dir_layout = self._build_directory_layout(root_path, files)

        print(dir_layout)
        
        # Build file contents
        file_contents = []
        
        for file_path in sorted(files):
            content = self._read_file_safely(file_path)
            if content is None:
                continue

            sanitized_content = self._sanitize_for_json(content)
            
            rel_path = file_path.relative_to(root_path)
            file_contents.append(f"\n+++ {rel_path} START +++\n")
            file_contents.append(sanitized_content)
            file_contents.append(f"\n+++ {rel_path} END +++\n")
        
        prompt = dir_layout + "".join(file_contents)
        return prompt
    
    def _sanitize_for_json(self, content: str) -> str:
        """Clean content for safe JSON embedding."""
        if not content:
            return ""
    
        # Remove null bytes and other problematic characters
        content = content.replace('\x00', '')
    
        # Normalize line endings
        content = content.replace('\r\n', '\n').replace('\r', '\n')
    
        # Ensure the string ends with a newline to avoid truncation issues
        if not content.endswith('\n'):
            content += '\n'
    
        return content
    
    def _call_deepseek_api(self, prompt: str) -> Optional[str]:
        """Call DeepSeek API with the prompt."""
        url = "https://api.deepseek.com/v1/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,
            "max_tokens": 4000,
            "stream": False
        }
        
        try:
            print("Calling DeepSeek API...", file=sys.stderr)
            response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=60)
            response.raise_for_status()
            
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except requests.exceptions.RequestException as e:
            print(f"API Error: {e}", file=sys.stderr)
            if hasattr(e, 'response') and e.response:
                print(f"Response: {e.response.text}", file=sys.stderr)
            return None
        except KeyError:
            print(f"Unexpected API response format", file=sys.stderr)
            return None
    
    def review(self, args) -> bool:
        """Main review method."""
        target_path = Path(args.target)
        
        if not target_path.exists():
            print(f"Error: Path '{target_path}' does not exist", file=sys.stderr)
            return False
        
        # Determine if we're reviewing a single file or directory
        is_file = target_path.is_file()
        
        # Load ignore patterns
        ignore_patterns = self._load_ignore_patterns(args.ignore_file)
        
        # Collect files
        files = list(self._collect_files(
            target_path,
            recursive=args.recursive,
            ignore_patterns=ignore_patterns,
            language_filter=args.language
        ))
        
        if not files:
            print("No files found to review", file=sys.stderr)
            return True
        
        print(f"Found {len(files)} files to review", file=sys.stderr)
        
        # Determine root path for relative paths
        if is_file:
            root_path = target_path.parent
        else:
            root_path = target_path
        
        # Build prompt
        prompt = self._build_prompt(root_path, files)
        
        # Call API
        response = self._call_deepseek_api(prompt)
        
        if response:
            print("\n" + "="*80)
            print("CODE REVIEW RESULTS")
            print("="*80 + "\n")
            print(response)
            return True
        else:
            return False


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Automatic Code Review Tool using DeepSeek API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s -f main.py
  %(prog)s -d src -r
  %(prog)s -d . -r -L python -i .gitignore
        """
    )
    
    # Create mutually exclusive group for file/directory
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "-f", "--file",
        dest="target",
        help="Review a single file"
    )
    mode_group.add_argument(
        "-d", "--directory",
        dest="target",
        help="Review all files in a directory"
    )
    
    parser.add_argument(
        "-r", "--recursive",
        action="store_true",
        help="Review files recursively in subdirectories"
    )
    
    parser.add_argument(
        "-L", "--language",
        help="Filter by programming language (e.g., python, javascript)"
    )
    
    parser.add_argument(
        "-i", "--ignore-file",
        help="File containing patterns to ignore (like .gitignore)"
    )
    
    return parser.parse_args()


def main():
    """Main entry point."""
    try:
        args = parse_arguments()
        reviewer = CodeReviewer()
        success = reviewer.review(args)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\nReview interrupted by user", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()