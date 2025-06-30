#!/usr/bin/env python3
"""
Dependency validation script for AutOps
Helps identify dependency conflicts before CI/CD runs
"""

import sys
import subprocess
import tempfile
import os
from pathlib import Path

def run_command(cmd, cwd=None):
    """Run a command and return result"""
    try:
        result = subprocess.run(
            cmd, 
            shell=True, 
            capture_output=True, 
            text=True, 
            cwd=cwd,
            timeout=300  # 5 minute timeout
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"

def validate_dependencies():
    """Validate that all dependencies can be resolved"""
    print("🔍 Validating AutOps dependencies...")
    
    # Get the project root
    project_root = Path(__file__).parent.parent
    pyproject_path = project_root / "pyproject.toml"
    
    if not pyproject_path.exists():
        print("❌ pyproject.toml not found!")
        return False
    
    print(f"📋 Using pyproject.toml: {pyproject_path}")
    
    # Create a temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"🧪 Testing in temporary directory: {temp_dir}")
        
        # Copy pyproject.toml to temp directory
        import shutil
        temp_pyproject = Path(temp_dir) / "pyproject.toml"
        shutil.copy2(pyproject_path, temp_pyproject)
        
        # Check if Poetry is available
        success, stdout, stderr = run_command("poetry --version")
        if not success:
            print("⚠️  Poetry not found, testing with pip...")
            
            # Create a simple requirements.txt from pyproject.toml for testing
            print("📝 Extracting dependencies for pip test...")
            
            # Read pyproject.toml and extract main dependencies
            import toml
            try:
                with open(pyproject_path, 'r') as f:
                    pyproject_data = toml.load(f)
                
                deps = pyproject_data.get('tool', {}).get('poetry', {}).get('dependencies', {})
                
                # Convert Poetry format to pip format (basic conversion)
                pip_deps = []
                for name, version in deps.items():
                    if name == 'python':
                        continue
                    if isinstance(version, str):
                        # Convert ^1.2.3 to >=1.2.3,<2.0.0
                        if version.startswith('^'):
                            major = version[1:].split('.')[0]
                            next_major = str(int(major) + 1)
                            pip_deps.append(f"{name}>={version[1:]},<{next_major}.0.0")
                        elif version.startswith('>='):
                            pip_deps.append(f"{name}{version}")
                        else:
                            pip_deps.append(f"{name}{version}")
                    elif isinstance(version, dict):
                        # Handle extras format like {extras = ["standard"], version = "^0.27.1"}
                        ver = version.get('version', '')
                        extras = version.get('extras', [])
                        if extras:
                            dep_name = f"{name}[{','.join(extras)}]"
                        else:
                            dep_name = name
                        
                        if ver.startswith('^'):
                            major = ver[1:].split('.')[0]
                            next_major = str(int(major) + 1)
                            pip_deps.append(f"{dep_name}>={ver[1:]},<{next_major}.0.0")
                        else:
                            pip_deps.append(f"{dep_name}{ver}")
                
                # Write requirements.txt
                req_file = Path(temp_dir) / "requirements.txt"
                with open(req_file, 'w') as f:
                    f.write('\n'.join(pip_deps))
                
                print(f"📦 Testing {len(pip_deps)} dependencies with pip...")
                
                # Test pip dependency resolution
                success, stdout, stderr = run_command(
                    f"pip install --dry-run --no-deps -r {req_file}",
                    cwd=temp_dir
                )
                
                if success:
                    print("✅ Pip dependency resolution: PASSED")
                else:
                    print("❌ Pip dependency resolution: FAILED")
                    print("STDERR:", stderr[:500])
                    return False
                    
            except Exception as e:
                print(f"❌ Error processing pyproject.toml: {e}")
                return False
        else:
            print(f"✅ Poetry found: {stdout.strip()}")
            
            # Test Poetry dependency resolution
            success, stdout, stderr = run_command(
                "poetry check",
                cwd=temp_dir
            )
            
            if success:
                print("✅ Poetry dependency check: PASSED")
            else:
                print("❌ Poetry dependency check: FAILED")
                print("STDERR:", stderr[:500])
                return False
            
            # Test lock file generation
            print("🔒 Testing lock file generation...")
            success, stdout, stderr = run_command(
                "poetry lock --no-update",
                cwd=temp_dir
            )
            
            if success:
                print("✅ Poetry lock generation: PASSED")
            else:
                print("❌ Poetry lock generation: FAILED")
                print("STDERR:", stderr[:500])
                return False
    
    print("🎉 All dependency validations passed!")
    return True

def main():
    """Main function"""
    try:
        # Import toml for parsing
        import toml
    except ImportError:
        print("Installing toml package for validation...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "toml"])
        import toml
    
    success = validate_dependencies()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main() 