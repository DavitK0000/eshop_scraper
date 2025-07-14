#!/usr/bin/env python3
"""
FFmpeg installation checker and helper script
"""

import subprocess
import sys
import platform
import os


def check_ffmpeg():
    """Check if FFmpeg is installed and accessible"""
    try:
        result = subprocess.run(['ffmpeg', '-version'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("✅ FFmpeg is installed and working!")
            print(f"Version: {result.stdout.split('ffmpeg version')[1].split()[0]}")
            return True
        else:
            print("❌ FFmpeg is installed but not working properly")
            return False
    except FileNotFoundError:
        print("❌ FFmpeg is not installed or not in PATH")
        return False
    except subprocess.TimeoutExpired:
        print("❌ FFmpeg check timed out")
        return False
    except Exception as e:
        print(f"❌ Error checking FFmpeg: {e}")
        return False


def get_installation_instructions():
    """Get installation instructions based on the operating system"""
    system = platform.system().lower()
    
    print("\n📋 FFmpeg Installation Instructions:")
    print("=" * 50)
    
    if system == "windows":
        print("""
Windows Installation:
1. Download FFmpeg from: https://ffmpeg.org/download.html#build-windows
2. Extract the downloaded zip file to a folder (e.g., C:\\ffmpeg)
3. Add the bin folder to your system PATH:
   - Right-click on 'This PC' → Properties → Advanced system settings
   - Click 'Environment Variables'
   - Under 'System variables', find 'Path' and click 'Edit'
   - Click 'New' and add the path to the bin folder (e.g., C:\\ffmpeg\\bin)
   - Click 'OK' on all dialogs
4. Restart your command prompt/terminal
5. Verify installation: ffmpeg -version
        """)
    
    elif system == "linux":
        print("""
Linux Installation (Ubuntu/Debian):
sudo apt update
sudo apt install ffmpeg

Linux Installation (CentOS/RHEL/Fedora):
sudo yum install ffmpeg
# or
sudo dnf install ffmpeg

Linux Installation (Arch):
sudo pacman -S ffmpeg

Verify installation: ffmpeg -version
        """)
    
    elif system == "darwin":  # macOS
        print("""
macOS Installation:
1. Install Homebrew (if not already installed):
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

2. Install FFmpeg:
   brew install ffmpeg

3. Verify installation: ffmpeg -version
        """)
    
    else:
        print(f"""
Unknown operating system: {system}
Please visit https://ffmpeg.org/download.html for installation instructions.
        """)


def main():
    """Main function"""
    print("🔍 Checking FFmpeg installation...")
    print("=" * 50)
    
    if check_ffmpeg():
        print("\n🎉 FFmpeg is ready for video processing!")
        print("\nYou can now use the video processing API endpoints:")
        print("- POST /api/v1/video/process")
        print("- GET /api/v1/video/tasks/{task_id}")
        print("- GET /api/v1/video/tasks")
        
        # Test basic FFmpeg functionality
        print("\n🧪 Testing basic FFmpeg functionality...")
        try:
            # Test if FFmpeg can handle common video formats
            result = subprocess.run([
                'ffmpeg', '-f', 'lavfi', '-i', 'testsrc=duration=1:size=320x240:rate=1',
                '-f', 'null', '-'
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                print("✅ FFmpeg can process videos successfully!")
            else:
                print("⚠️  FFmpeg test failed, but installation seems correct")
                print(f"Error: {result.stderr}")
                
        except Exception as e:
            print(f"⚠️  Could not test FFmpeg functionality: {e}")
            
    else:
        get_installation_instructions()
        
        print("\n💡 After installing FFmpeg:")
        print("1. Restart your terminal/command prompt")
        print("2. Run this script again to verify installation")
        print("3. Start your API server")
        
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main()) 