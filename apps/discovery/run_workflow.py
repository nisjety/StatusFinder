#!/usr/bin/env python
"""
Workflow Spider Runner for Discovery Project

This script provides a simplified way to run the workflow spider with the correct settings.
It automatically sets up the asyncio reactor and handles Playwright configuration.

Usage:
  python run_workflow.py https://example.com
  python run_workflow.py https://example.com --debug
"""
import sys
import os
import time
import argparse
from pathlib import Path

def main():
    """Parse arguments and run the workflow spider with proper settings."""
    parser = argparse.ArgumentParser(description="Run the Discovery workflow spider")
    parser.add_argument("url", help="The URL to crawl")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode (no browser UI)")
    parser.add_argument("--workflow", help="Specify a workflow to run")
    
    args = parser.parse_args()
    
    print(f"Discovery Workflow Spider Runner")
    print(f"===============================")
    print(f"URL: {args.url}")
    print(f"Debug mode: {'enabled' if args.debug else 'disabled'}")
    print(f"Browser mode: {'headless' if args.headless else 'visible'}")
    if args.workflow:
        print(f"Workflow: {args.workflow}")
    print(f"Starting in 1 second...")
    time.sleep(1)
    
    # Activate the virtual environment if needed
    venv_activate = Path(__file__).parent / "venv" / "bin" / "activate"
    if venv_activate.exists():
        print(f"Virtual environment found at: {venv_activate}")
        print(f"Make sure to activate it with: source {venv_activate}")
    
    # Build the command
    cmd = [
        "cd", str(Path(__file__).parent), "&&",
        # First set asyncio reactor via environment variable
        "SCRAPY_SETTINGS_MODULE=discovery.settings.development",
        "TWISTED_REACTOR=twisted.internet.asyncioreactor.AsyncioSelectorReactor",
        # Then run scrapy
        "scrapy", "crawl", "workflow", 
        # URL parameter
        "-a", f"start_urls={args.url}"
    ]
    
    # Optional arguments
    if args.debug:
        cmd.append("--loglevel=DEBUG")
    if args.workflow:
        cmd.extend(["-a", f"workflow={args.workflow}"])
    if args.headless:
        cmd.extend(["-a", "headless=true"]) 
    
    # Show the command
    print("\nCommand to run manually:")
    print(" ".join(cmd))
    print("\nPress Ctrl+C to stop the crawler at any time.")
    
    # Run the command
    try:
        os.system(" ".join(cmd))
    except KeyboardInterrupt:
        print("\nCrawling stopped by user.")

if __name__ == "__main__":
    main()
