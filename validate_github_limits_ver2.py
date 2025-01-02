#!/usr/bin/env python3
"""
GitHub Repository Validator
Validates and manages repository content against GitHub limits with automated file relocation.
"""

import os
import shutil
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List

REPO_DIR = "~/code/IBM-Notre-Dame-Tech-Ethics-Lab-GenAI-Predict-Human-Behavior"
LARGE_BACKUP_DIR = "/media/data2"
FLAG_AUTOMOVE_LARGE = True

# GitHub Platform Limits
MAX_GITHUB_FILESIZE_MB = 100
MAX_GITHUB_FILESIZE_WARNING_MB = 50 
MAX_GITHUB_FILES_PER_DIR = 1000
MAX_GITHUB_REPO_SIZE_GB = 100
MAX_GITHUB_REPO_WARNING_GB = 5
MAX_GITHUB_REPO_RECOMMENDED_GB = 1

class GitHubValidator:
    """Validates repository against GitHub limits with automated file management."""

    def __init__(self, repo_dir: str, backup_dir: str, auto_move: bool = False):
        """Initialize validator with repository and backup locations.
        
        Args:
            repo_dir: Repository root directory path
            backup_dir: Directory for relocated large files
            auto_move: Enable automatic file relocation
        """
        self.repo_dir = Path(repo_dir).resolve()
        self.backup_dir = Path(backup_dir).resolve()
        self.auto_move = auto_move
        self.timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.report_file = f"report_github_{self.timestamp}.txt"
        self.issues: List[str] = []

        self._setup_logging()

    def _setup_logging(self) -> None:
        """Configure dual logging to console and file."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(self.report_file)
            ]
        )

    def check_file_sizes(self) -> None:
        """Scan repository for files exceeding GitHub size limits."""
        try:
            for path in self.repo_dir.rglob('*'):
                if path.is_file() and not path.is_symlink():
                    size_mb = path.stat().st_size / (1024 * 1024)
                    self._handle_file_size(path, size_mb)
        except Exception as e:
            logging.error(f"File size check error: {e}")





    def _handle_file_size(self, path: Path, size_mb: float) -> None:
        """Process files based on size thresholds."""
        rel_path = path.relative_to(self.repo_dir)
        if size_mb > MAX_GITHUB_FILESIZE_MB:
            msg = f"ERROR: {rel_path} is {size_mb:.1f}MB (max {MAX_GITHUB_FILESIZE_MB}MB)"
            self.issues.append(msg)
            logging.error(msg)
            if self.auto_move:
                self.move_large_file(path)
        elif size_mb > MAX_GITHUB_FILESIZE_WARNING_MB:
            msg = f"WARNING: {rel_path} is {size_mb:.1f}MB"
            self.issues.append(msg)
            logging.warning(msg)




    def check_dir_file_counts(self) -> None:
        """Verify directory file counts against GitHub display limits."""
        try:
            for path in self.repo_dir.rglob('*'):
                if path.is_dir():
                    files = list(path.glob('*'))
                    if len(files) > MAX_GITHUB_FILES_PER_DIR:
                        msg = f"WARNING: {path.relative_to(self.repo_dir)} has {len(files)} files"
                        self.issues.append(msg)
                        logging.warning(msg)
        except Exception as e:
            logging.error(f"Directory check error: {e}")

    def check_repo_size(self) -> None:
        """Calculate and validate total repository size."""
        try:
            total_size_gb = sum(
                f.stat().st_size for f in self.repo_dir.rglob('*') 
                if f.is_file() and not f.is_symlink()
            ) / (1024**3)
            
            if total_size_gb > MAX_GITHUB_REPO_SIZE_GB:
                msg = f"ERROR: Repo is {total_size_gb:.1f}GB (max {MAX_GITHUB_REPO_SIZE_GB}GB)"
                self.issues.append(msg)
                logging.error(msg)
            elif total_size_gb > MAX_GITHUB_REPO_WARNING_GB:
                msg = f"WARNING: Repo is {total_size_gb:.1f}GB (recommended < {MAX_GITHUB_REPO_RECOMMENDED_GB}GB)"
                self.issues.append(msg)
                logging.warning(msg)
        except Exception as e:
            logging.error(f"Repository size check error: {e}")


    def move_large_file(self, file_path: Path) -> None:
        """Relocate file to backup directory and create symlink, preserving timestamps."""
        try:
            rel_path = file_path.relative_to(self.repo_dir)
            backup_path = self.backup_dir / rel_path
            
            # Create backup directory structure
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Get original timestamps
            stat = file_path.stat()
            atime = stat.st_atime
            mtime = stat.st_mtime
            
            # Move file and create symlink
            shutil.move(str(file_path), str(backup_path))
            os.symlink(str(backup_path), str(file_path))
            
            # Restore timestamps on both symlink and moved file
            os.utime(str(backup_path), (atime, mtime))
            os.utime(str(file_path), (atime, mtime), follow_symlinks=False)
            
            size_mb = stat.st_size / (1024 * 1024)
            msg = f"📦 Moved large file ({size_mb:.1f}MB):\n  From: {rel_path}\n  To: {backup_path}"
            self.issues.append(msg)
            logging.info(msg)
            
        except Exception as e:
            logging.error(f"Failed to move {file_path}: {e}")
            raise


    def validate(self) -> None:
        """Run all repository validation checks."""
        logging.info(f"GitHub Repository Validation Report - {self.timestamp}")
        
        self.check_file_sizes()
        self.check_dir_file_counts()
        self.check_repo_size()
        
        if not self.issues:
            logging.info("No GitHub limit violations found")

def main():
   """Entry point for repository validation."""

   validator = GitHubValidator(REPO_DIR, LARGE_BACKUP_DIR, FLAG_AUTOMOVE_LARGE)
   validator.validate()

if __name__ == '__main__':
   main()