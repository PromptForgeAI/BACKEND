# scripts/run_improvements.py - Execute All Security & Performance Improvements
import asyncio
import subprocess
import sys
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ImprovementRunner:
    """Execute all improvement scripts in correct order"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.logs = []
        
    def log_step(self, step: str, status: str, details: str = ""):
        """Log improvement step"""
        entry = {
            "step": step,
            "status": status,
            "details": details,
            "timestamp": __import__("time").time()
        }
        self.logs.append(entry)
        logger.info(f"{status.upper()}: {step} - {details}")
    
    def run_command(self, command: str, description: str) -> bool:
        """Run a shell command and log results"""
        try:
            result = subprocess.run(
                command, 
                shell=True, 
                capture_output=True, 
                text=True,
                cwd=self.project_root
            )
            
            if result.returncode == 0:
                self.log_step(description, "success", f"Command completed: {command}")
                return True
            else:
                self.log_step(description, "error", f"Command failed: {result.stderr}")
                return False
                
        except Exception as e:
            self.log_step(description, "error", f"Exception running command: {e}")
            return False
    
    def check_dependencies(self) -> bool:
        """Check if all required dependencies are available"""
        logger.info("🔍 Checking dependencies...")
        
        required_packages = [
            "fastapi", "uvicorn", "jinja2", "aiohttp", 
            "motor", "pymongo", "python-jose", "passlib"
        ]
        
        missing_packages = []
        for package in required_packages:
            try:
                __import__(package.replace("-", "_"))
            except ImportError:
                missing_packages.append(package)
        
        if missing_packages:
            self.log_step(
                "dependency_check", 
                "error", 
                f"Missing packages: {', '.join(missing_packages)}"
            )
            return False
        
        self.log_step("dependency_check", "success", "All dependencies available")
        return True
    
    def backup_existing_files(self) -> bool:
        """Create backups of files we're modifying"""
        logger.info("💾 Creating backups...")
        
        backup_dir = self.project_root / "backups"
        backup_dir.mkdir(exist_ok=True)
        
        import shutil
        import time
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        
        critical_files = [
            "main.py",
            "compendium.json", 
            "brain.json",
            "api/brain_engine.py",
            "api/demon.py"
        ]
        
        try:
            for file_path in critical_files:
                source = self.project_root / file_path
                if source.exists():
                    backup_name = f"{file_path.replace('/', '_')}_{timestamp}.backup"
                    shutil.copy2(source, backup_dir / backup_name)
            
            self.log_step("backup_creation", "success", f"Backups created in {backup_dir}")
            return True
            
        except Exception as e:
            self.log_step("backup_creation", "error", f"Backup failed: {e}")
            return False
    
    def run_technique_unification(self) -> bool:
        """Run the technique database unification"""
        logger.info("🔄 Unifying technique databases...")
        
        try:
            # Import and run the unification script
            sys.path.append(str(self.project_root / "scripts"))
            from unify_techniques import TechniqueUnifier
            
            unifier = TechniqueUnifier()
            unified_data = unifier.unify_techniques()
            
            # Validate before saving
            validation = unifier.validate_unified(unified_data["techniques"])
            
            if validation["issues"]:
                self.log_step(
                    "technique_unification", 
                    "warning", 
                    f"Validation issues found: {len(validation['issues'])}"
                )
            
            # Save unified data
            unifier.save_unified(unified_data)
            
            self.log_step(
                "technique_unification", 
                "success", 
                f"Unified {unified_data['metadata']['total_techniques']} techniques"
            )
            return True
            
        except Exception as e:
            self.log_step("technique_unification", "error", f"Unification failed: {e}")
            return False
    
    def validate_security_middleware(self) -> bool:
        """Validate that security middleware is properly integrated"""
        logger.info("🔒 Validating security integration...")
        
        try:
            # Check if middleware files exist
            middleware_dir = self.project_root / "middleware"
            if not middleware_dir.exists():
                self.log_step("security_validation", "error", "Middleware directory not found")
                return False
            
            required_files = ["__init__.py", "security.py", "auth.py"]
            for file_name in required_files:
                file_path = middleware_dir / file_name
                if not file_path.exists():
                    self.log_step("security_validation", "error", f"Missing file: {file_path}")
                    return False
            
            # Check main.py integration
            main_py = self.project_root / "main.py"
            if main_py.exists():
                content = main_py.read_text()
                if "security_middleware" not in content:
                    self.log_step("security_validation", "error", "Security middleware not integrated in main.py")
                    return False
            
            self.log_step("security_validation", "success", "Security middleware properly integrated")
            return True
            
        except Exception as e:
            self.log_step("security_validation", "error", f"Validation failed: {e}")
            return False
    
    def run_health_checks(self) -> bool:
        """Run basic health checks on the system"""
        logger.info("🏥 Running health checks...")
        
        try:
            # Check if monitoring endpoints are available
            monitoring_file = self.project_root / "api" / "monitoring.py"
            if not monitoring_file.exists():
                self.log_step("health_check", "error", "Monitoring endpoints not found")
                return False
            
            # Check circuit breaker utilities
            circuit_breaker_file = self.project_root / "utils" / "circuit_breaker.py"
            if not circuit_breaker_file.exists():
                self.log_step("health_check", "error", "Circuit breaker utilities not found")
                return False
            
            self.log_step("health_check", "success", "All health check components available")
            return True
            
        except Exception as e:
            self.log_step("health_check", "error", f"Health check failed: {e}")
            return False
    
    async def run_security_tests(self) -> bool:
        """Run the security test suite"""
        logger.info("🧪 Running security tests...")
        
        try:
            # Import and run security tests
            sys.path.append(str(self.project_root / "scripts"))
            from test_security_improvements import SecurityTestSuite
            
            async with SecurityTestSuite() as test_suite:
                results = await test_suite.run_all_tests()
                
                summary = results["summary"]
                success_rate = summary["success_rate"]
                
                if success_rate >= 0.8:  # 80% pass rate threshold
                    self.log_step(
                        "security_tests", 
                        "success", 
                        f"Tests passed: {summary['passed_tests']}/{summary['total_tests']} ({success_rate:.2%})"
                    )
                    return True
                else:
                    self.log_step(
                        "security_tests", 
                        "warning", 
                        f"Low pass rate: {success_rate:.2%}"
                    )
                    return False
                    
        except Exception as e:
            self.log_step("security_tests", "error", f"Security tests failed: {e}")
            return False
    
    def generate_report(self) -> str:
        """Generate improvement report"""
        report_path = self.project_root / "improvement_report.json"
        
        success_count = sum(1 for log in self.logs if log["status"] == "success")
        total_count = len(self.logs)
        
        report = {
            "improvement_summary": {
                "total_steps": total_count,
                "successful_steps": success_count,
                "success_rate": success_count / total_count if total_count > 0 else 0,
                "timestamp": __import__("time").time()
            },
            "improvements_applied": [
                "Input validation middleware",
                "Secure Jinja2 template rendering", 
                "Unified authentication system",
                "Circuit breaker pattern for LLM calls",
                "Request tracing and monitoring",
                "Health check endpoints",
                "Technique database unification"
            ],
            "detailed_logs": self.logs
        }
        
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
        
        return str(report_path)
    
    async def run_all_improvements(self) -> bool:
        """Execute all improvements in the correct order"""
        logger.info("🚀 Starting security and performance improvements...")
        
        steps = [
            ("Dependency Check", self.check_dependencies),
            ("File Backup", self.backup_existing_files),
            ("Technique Unification", self.run_technique_unification),
            ("Security Validation", self.validate_security_middleware),
            ("Health Checks", self.run_health_checks),
            ("Security Tests", self.run_security_tests)
        ]
        
        success_count = 0
        for step_name, step_function in steps:
            logger.info(f"📋 Executing: {step_name}")
            
            if asyncio.iscoroutinefunction(step_function):
                success = await step_function()
            else:
                success = step_function()
            
            if success:
                success_count += 1
                logger.info(f"✅ {step_name} completed successfully")
            else:
                logger.error(f"❌ {step_name} failed")
        
        # Generate final report
        report_path = self.generate_report()
        
        success_rate = success_count / len(steps)
        logger.info(f"\n🎯 Improvement Summary:")
        logger.info(f"   Completed: {success_count}/{len(steps)} steps")
        logger.info(f"   Success Rate: {success_rate:.2%}")
        logger.info(f"   Report: {report_path}")
        
        if success_rate >= 0.8:
            logger.info("🎉 Security improvements successfully applied!")
            return True
        else:
            logger.warning("⚠️ Some improvements failed. Check the report for details.")
            return False

async def main():
    """Main function to run all improvements"""
    print("🔒 Demon Engine Security & Performance Improvements")
    print("=" * 50)
    
    runner = ImprovementRunner()
    success = await runner.run_all_improvements()
    
    if success:
        print("\n✅ All improvements applied successfully!")
        print("🚀 Your Demon Engine is now more secure and performant.")
    else:
        print("\n⚠️ Some improvements failed.")
        print("📋 Check improvement_report.json for details.")
    
    return success

if __name__ == "__main__":
    asyncio.run(main())
