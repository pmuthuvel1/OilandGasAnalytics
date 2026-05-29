#!/usr/bin/env python3
"""
Verification script for Oil & Gas Analytics upgrade to Python 3.12
Checks all dependencies and imports are working correctly
"""

import sys
import subprocess
from typing import Dict, List, Tuple

def print_header(text: str) -> None:
    """Print formatted header"""
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")

def check_python_version() -> bool:
    """Verify Python 3.12+"""
    version_info = sys.version_info
    version_str = f"{version_info.major}.{version_info.minor}.{version_info.micro}"
    
    print(f"Python Version: {version_str}")
    
    if version_info.major == 3 and version_info.minor >= 12:
        print("✅ Python 3.12+ detected")
        return True
    else:
        print(f"❌ Python 3.12+ required (found {version_info.major}.{version_info.minor})")
        return False

def check_package_versions() -> Dict[str, Tuple[bool, str]]:
    """Check versions of critical packages"""
    packages = {
        'langgraph': '0.2.11',
        'langchain': '0.2.15',
        'langchain_openai': '0.2.2',
        'fastapi': '0.115.3',
        'pydantic': '2.9.2',
        'numpy': '2.0.0',
        'pandas': '2.2.3',
    }
    
    results = {}
    
    for package, expected_version in packages.items():
        try:
            module = __import__(package)
            actual_version = getattr(module, '__version__', 'unknown')
            
            # For submodules, get the version correctly
            if package == 'langchain_openai':
                import langchain_openai
                actual_version = langchain_openai.__version__
            
            major_minor_expected = '.'.join(expected_version.split('.')[:2])
            major_minor_actual = '.'.join(actual_version.split('.')[:2])
            
            is_correct = major_minor_actual >= major_minor_expected
            results[package] = (is_correct, actual_version)
            
            status = "✅" if is_correct else "⚠️"
            print(f"{status} {package}: {actual_version} (expected: {expected_version}+)")
        except ImportError:
            results[package] = (False, "NOT INSTALLED")
            print(f"❌ {package}: NOT INSTALLED")
    
    return results

def check_imports() -> bool:
    """Test critical imports"""
    print_header("Testing Imports")
    
    tests = [
        ("LangGraph StateGraph", "from langgraph.graph import StateGraph, END"),
        ("LangChain Core Prompts", "from langchain_core.prompts import ChatPromptTemplate"),
        ("LangChain Core Tools", "from langchain_core.tools import tool"),
        ("LangChain Agents", "from langchain.agents import create_openai_functions_agent"),
        ("LangChain OpenAI", "from langchain_openai import ChatOpenAI"),
        ("FastAPI", "from fastapi import FastAPI"),
        ("Pydantic", "from pydantic import BaseModel"),
        ("NumPy", "import numpy as np"),
        ("Pandas", "import pandas as pd"),
    ]
    
    all_passed = True
    
    for name, import_stmt in tests:
        try:
            exec(import_stmt)
            print(f"✅ {name}")
        except Exception as e:
            print(f"❌ {name}: {str(e)}")
            all_passed = False
    
    return all_passed

def check_app_imports() -> bool:
    """Test application imports"""
    print_header("Testing Application Imports")
    
    app_tests = [
        ("Config", "from app.config import get_config"),
        ("Tools", "from app.tools import TOOLS"),
        ("Agents", "from app.agents import create_seismic_analyzer_agent"),
        ("Workflows", "from app.workflows import WorkflowOrchestrator"),
    ]
    
    all_passed = True
    
    for name, import_stmt in app_tests:
        try:
            exec(import_stmt)
            print(f"✅ {name}")
        except Exception as e:
            print(f"❌ {name}: {str(e)}")
            all_passed = False
    
    return all_passed

def check_config() -> bool:
    """Test configuration loading"""
    print_header("Testing Configuration")
    
    try:
        from app.config import get_config
        config = get_config()
        
        print(f"✅ Configuration loaded successfully")
        print(f"   - API Port: {config.API_PORT}")
        print(f"   - UI Port: {config.UI_PORT}")
        print(f"   - OpenAI Model: {config.OPENAI_MODEL}")
        print(f"   - Max Iterations: {config.MAX_ITERATIONS}")
        return True
    except Exception as e:
        print(f"❌ Configuration error: {str(e)}")
        return False

def check_pydantic_models() -> bool:
    """Test Pydantic models"""
    print_header("Testing Pydantic Models")
    
    try:
        from app.tools import SeismicData, WellLogData, AnalysisResult
        
        # Test creating instances
        seismic = SeismicData(
            well_name="Test",
            depth_values=[0, 100, 200],
            amplitude_values=[10, 20, 30],
            frequency_content={"low": 0.5, "high": 0.5}
        )
        print("✅ SeismicData model")
        
        well = WellLogData(
            well_name="Test",
            depth_values=[0, 100, 200],
            gamma_ray=[50, 60, 70],
            resistivity=[100, 120, 140],
            porosity=[0.2, 0.25, 0.3]
        )
        print("✅ WellLogData model")
        
        result = AnalysisResult(
            agent_name="test",
            analysis_type="test",
            confidence=0.95,
            findings={"test": "result"}
        )
        print("✅ AnalysisResult model")
        
        return True
    except Exception as e:
        print(f"❌ Pydantic models error: {str(e)}")
        return False

def main():
    """Run all verification checks"""
    print_header("Oil & Gas Analytics Upgrade Verification")
    
    # Run checks
    checks = [
        ("Python Version", check_python_version),
        ("Package Versions", lambda: bool(check_package_versions())),
        ("Library Imports", check_imports),
        ("Application Imports", check_app_imports),
        ("Configuration", check_config),
        ("Pydantic Models", check_pydantic_models),
    ]
    
    results = []
    
    for name, check_func in checks:
        print_header(f"Checking {name}")
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ Error during {name}: {str(e)}")
            results.append((name, False))
    
    # Summary
    print_header("Verification Summary")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅" if result else "❌"
        print(f"{status} {name}")
    
    print(f"\nResult: {passed}/{total} checks passed")
    
    if passed == total:
        print("\n🎉 All checks passed! Your upgrade is complete and working correctly.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} check(s) failed. Please review the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
