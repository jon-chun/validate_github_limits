#!/usr/bin/env python3
"""GitHub Repository Validator"""

import os
import shutil
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, field

@dataclass
class GitHubLimits:
    MAX_FILESIZE_MB: float = 100.0
    WARNING_FILESIZE_MB: float = 50.0 
    MAX_FILES_PER_DIR: int = 1000
    MAX_REPO_SIZE_GB: float = 100.0
    WARNING_REPO_SIZE_GB: float = 5.0
    RECOMMENDED_REPO_SIZE_GB: float = 1.0

@dataclass
class ValidationStats:
    total_files: int = 0
    total_size_gb: float = 0
    large_files: List[Tuple[Path, float]] = field(default_factory=list)
    warning_files: List[Tuple[Path, float]] = field(default_factory=list)
    large_dirs: List[Tuple[Path, int]] = field(default_factory=list)

class GitHubValidator:
    def __init__(self, repo_dir: str, backup_dir: str, auto_move: bool = False):
        self.repo_dir = Path(os.path.expanduser(repo_dir)).resolve()
        self.backup_dir = Path(backup_dir).resolve()
        self.auto_move = auto_move
        self.timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.report_file = f"github_validation_{self.timestamp}.txt"
        self.issues: List[str] = []
        self.limits = GitHubLimits()
        self.stats = ValidationStats()
        self.critical_dirs = ['src', 'data']
        self._setup_logging()

    def _setup_logging(self) -> None:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(self.report_file)
            ]
        )

    def log_header(self, section: str) -> None:
        logging.info(f"\n{'='*80}\n{section}\n{'='*80}")

    def check_file_sizes(self) -> None:
        self.log_header("FILE SIZES")
        logging.info(f"Limits: Max = {self.limits.MAX_FILESIZE_MB}MB, Warning = {self.limits.WARNING_FILESIZE_MB}MB\n")
        
        try:
            for subdir in self.critical_dirs:
                dir_path = self.repo_dir / subdir
                if dir_path.exists():
                    logging.info(f"\nScanning /{subdir} directory:")
                    for path in dir_path.rglob('*'):
                        if path.is_file() and not path.is_symlink():
                            self.stats.total_files += 1
                            size_mb = path.stat().st_size / (1024 * 1024)
                            self._handle_file_size(path, size_mb)

            logging.info("\nScanning remaining repository files:")
            for path in self.repo_dir.rglob('*'):
                if path.is_file() and not path.is_symlink():
                    if not any(str(path).startswith(str(self.repo_dir / d)) for d in self.critical_dirs):
                        self.stats.total_files += 1
                        size_mb = path.stat().st_size / (1024 * 1024)
                        self._handle_file_size(path, size_mb)

            if not self.stats.large_files and not self.stats.warning_files:
                logging.info("✓ No files exceed size limits")
        except Exception as e:
            logging.error(f"File size check error: {e}")
            raise

    def _handle_file_size(self, path: Path, size_mb: float) -> None:
        rel_path = path.relative_to(self.repo_dir)
        if size_mb > self.limits.MAX_FILESIZE_MB:
            msg = f"ERROR: {rel_path} is {size_mb:.1f}MB (max {self.limits.MAX_FILESIZE_MB}MB)"
            self.stats.large_files.append((path, size_mb))
            self.issues.append(msg)
            logging.error(msg)
            if self.auto_move:
                self.move_large_file(path)
        elif size_mb > self.limits.WARNING_FILESIZE_MB:
            msg = f"WARNING: {rel_path} is {size_mb:.1f}MB"
            self.stats.warning_files.append((path, size_mb))
            self.issues.append(msg)
            logging.warning(msg)

    def move_large_file(self, file_path: Path) -> None:
        try:
            rel_path = file_path.relative_to(self.repo_dir)
            backup_path = self.backup_dir / rel_path
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            
            stat = file_path.stat()
            atime, mtime = stat.st_atime, stat.st_mtime
            size_mb = stat.st_size / (1024 * 1024)
            
            shutil.move(str(file_path), str(backup_path))
            os.symlink(str(backup_path), str(file_path))
            
            os.utime(str(backup_path), (atime, mtime))
            os.utime(str(file_path), (atime, mtime), follow_symlinks=False)
            
            msg = f"📦 Moved large file ({size_mb:.1f}MB):\n  From: {rel_path}\n  To: {backup_path}"
            self.issues.append(msg)
            logging.info(msg)
        except Exception as e:
            logging.error(f"Failed to move {file_path}: {e}")
            raise

    def check_dir_file_counts(self) -> None:
        """Verify directory file counts against GitHub display limits."""
        self.log_header("DIRECTORY FILE COUNTS")
        logging.info(f"Limit: Max {self.limits.MAX_FILES_PER_DIR} files per directory\n")
        
        try:
            for path in self.repo_dir.rglob('*'):
                if path.is_dir():
                    files = list(path.glob('*'))
                    count = len(files)
                    if count > self.limits.MAX_FILES_PER_DIR:
                        rel_path = path.relative_to(self.repo_dir)
                        msg = f"⚠️ WARNING: {rel_path} contains {count} files"
                        self.stats.large_dirs.append((path, count))
                        self.issues.append(msg)
                        logging.warning(msg)
                        
            if not self.stats.large_dirs:
                logging.info("✓ No directories exceed file count limit")
        except Exception as e:
            logging.error(f"Directory check error: {e}")
            raise

    def check_repo_size(self) -> None:
        """Calculate and validate total repository size."""
        self.log_header("REPOSITORY SIZE")
        logging.info(f"Limits: Max = {self.limits.MAX_REPO_SIZE_GB}GB")
        logging.info(f"        Warning = {self.limits.WARNING_REPO_SIZE_GB}GB")
        logging.info(f"        Recommended < {self.limits.RECOMMENDED_REPO_SIZE_GB}GB\n")
        
        try:
            total_bytes = sum(
                f.stat().st_size for f in self.repo_dir.rglob('*') 
                if f.is_file() and not f.is_symlink()
            )
            self.stats.total_size_gb = total_bytes / (1024**3)
            
            if self.stats.total_size_gb > self.limits.MAX_REPO_SIZE_GB:
                msg = f"❌ ERROR: Repository size is {self.stats.total_size_gb:.1f}GB"
                self.issues.append(msg)
                logging.error(msg)
            elif self.stats.total_size_gb > self.limits.WARNING_REPO_SIZE_GB:
                msg = f"⚠️ WARNING: Repository size is {self.stats.total_size_gb:.1f}GB"
                self.issues.append(msg)
                logging.warning(msg)
            else:
                logging.info(f"✓ Repository size {self.stats.total_size_gb:.1f}GB is within limits")
        except Exception as e:
            logging.error(f"Repository size check error: {e}")
            raise

    def validate(self) -> None:
        """Run all repository validation checks."""
        self.log_header("GitHub Repository Validation Report")
        logging.info(f"Repository: {self.repo_dir}")
        logging.info(f"Auto-move large files: {self.auto_move}\n")
        
        self.check_file_sizes()
        self.check_dir_file_counts()
        self.check_repo_size()
        
        self.log_header("VALIDATION SUMMARY")
        logging.info(f"Total files scanned: {self.stats.total_files}")
        logging.info(f"Large files found: {len(self.stats.large_files)}")
        logging.info(f"Warning files found: {len(self.stats.warning_files)}")
        logging.info(f"Total issues found: {len(self.issues)}")
        logging.info(f"\nDetailed report saved to: {self.report_file}")

def main():
    REPO_DIR = "~/code/IBM-Notre-Dame-Tech-Ethics-Lab-GenAI-Predict-Human-Behavior"
    LARGE_BACKUP_DIR = "/media/data2/github_large_files"
    FLAG_AUTOMOVE_LARGE = True

    validator = GitHubValidator(REPO_DIR, LARGE_BACKUP_DIR, FLAG_AUTOMOVE_LARGE)
    validator.validate()

if __name__ == '__main__':
    main()