#!/usr/bin/env python3
"""
Domain Update Script for Stock Assist
=====================================

This script helps you update all domain references, social media handles,
and contact information throughout the Stock Assist codebase.

Usage:
    python update_domains.py --domain your-domain.com --github your-github --discord your-discord

Example:
    python update_domains.py --domain myfinanceapp.com --github myusername --discord mydiscord123

What this script updates:
- All "yourdomain.com" references to your actual domain
- GitHub username references (@vibheksoni to @yourusername)
- Discord username references (1codec to yourdiscord)
- Email addresses (if --email is provided)
"""

import argparse
import os
import re
import sys
from pathlib import Path
from typing import List, Tuple


def find_files_to_update() -> List[Path]:
    """Find all files that need domain/contact updates."""
    extensions = ['.py', '.js', '.html', '.md', '.json', '.yml', '.yaml', '.env.example']
    exclude_dirs = {'.git', '__pycache__', 'node_modules', '.venv', 'venv', 'env'}
    
    files = []
    for root, dirs, filenames in os.walk('.'):
        # Remove excluded directories
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        for filename in filenames:
            file_path = Path(root) / filename
            if file_path.suffix in extensions:
                files.append(file_path)
    
    return files


def update_file_content(file_path: Path, replacements: List[Tuple[str, str]]) -> bool:
    """Update file content with the given replacements."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        for old_text, new_text in replacements:
            content = content.replace(old_text, new_text)
        
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        
        return False
    
    except Exception as e:
        print(f"Error updating {file_path}: {e}")
        return False


def generate_secure_password() -> str:
    """Generate a secure password for database."""
    import secrets
    import string
    
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    password = ''.join(secrets.choice(alphabet) for _ in range(16))
    return password


def main():
    parser = argparse.ArgumentParser(description='Update domain and contact information in Stock Assist')
    parser.add_argument('--domain', required=True, help='Your domain name (e.g., myfinanceapp.com)')
    parser.add_argument('--github', help='Your GitHub username (without @)')
    parser.add_argument('--discord', help='Your Discord username')
    parser.add_argument('--email', help='Your email address')
    parser.add_argument('--replace-original', action='store_true', 
                       help='Replace yourdomain.com with your domain (for production deployment)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be changed without making changes')
    
    args = parser.parse_args()
    
    # Validate domain
    if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9-]*[a-zA-Z0-9]*\.[a-zA-Z]{2,}$', args.domain):
        print(f"Error: '{args.domain}' is not a valid domain name")
        sys.exit(1)
    
    # Prepare replacements
    replacements = [
        ('yourdomain.com', args.domain),
        ('your-domain.com', args.domain),
        ('your-actual-domain.com', args.domain),
    ]
    
    if args.replace_original:
        replacements.append(('yourdomain.com', args.domain))
    
    if args.github:
        replacements.extend([
            ('@vibheksoni', f'@{args.github}'),
            ('vibheksoni', args.github),
        ])
    
    if args.discord:
        replacements.append(('1codec', args.discord))
    
    if args.email:
        replacements.extend([
            ('admin@yourdomain.com', f'admin@{args.domain}'),
            ('SET-YOUR-EMAIL', args.email),
            ('YOUR-EMAIL', args.email),
        ])
    
    # Add secure password suggestions
    db_password = generate_secure_password()
    app_password = generate_secure_password()
    
    print("🔧 Stock Assist Domain Update Script")
    print("=" * 40)
    print(f"Domain: {args.domain}")
    if args.github:
        print(f"GitHub: @{args.github}")
    if args.discord:
        print(f"Discord: {args.discord}")
    if args.email:
        print(f"Email: {args.email}")
    print(f"Replace original domain: {args.replace_original}")
    print(f"Dry run: {args.dry_run}")
    print()
    
    # Generate secure passwords
    print("🔐 Generated Secure Passwords:")
    print(f"MySQL Root Password: {db_password}")
    print(f"MySQL App Password: {app_password}")
    print()
    print("⚠️  IMPORTANT: Save these passwords securely and update them in:")
    print("   - docker-compose.yml")
    print("   - setup.sql")
    print("   - .env file")
    print()
    
    if not args.dry_run:
        confirm = input("Continue with updates? (y/N): ")
        if confirm.lower() != 'y':
            print("Aborted.")
            sys.exit(0)
    
    # Find and update files
    files = find_files_to_update()
    updated_files = []
    
    for file_path in files:
        if args.dry_run:
            # Just check what would be changed
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                would_change = False
                for old_text, new_text in replacements:
                    if old_text in content:
                        would_change = True
                        break
                
                if would_change:
                    print(f"Would update: {file_path}")
            except:
                pass
        else:
            if update_file_content(file_path, replacements):
                updated_files.append(file_path)
                print(f"Updated: {file_path}")
    
    if not args.dry_run:
        print(f"\n✅ Updated {len(updated_files)} files")
        print("\n🔧 Next Steps:")
        print("1. Update passwords in docker-compose.yml and setup.sql")
        print("2. Update .env file with your API keys and configuration")
        print("3. Test your configuration with: docker-compose up -d")
        print("4. Check that all services start correctly")
    else:
        print(f"\n📋 Dry run complete. Would update files shown above.")


if __name__ == '__main__':
    main()
