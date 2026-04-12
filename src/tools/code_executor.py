"""Code execution tools"""
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class CodeExecutor:
    """
    Safe code execution tool
    
    Warning: Only use with trusted code!
    """
    
    @staticmethod
    async def execute_python(code: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute Python code with provided context
        
        Args:
            code: Python code to execute
            context: Variables available to code
            
        Returns:
            Execution result with output and any errors
        """
        if context is None:
            context = {}
        
        try:
            result = {}
            exec(code, context, result)
            
            return {
                "success": True,
                "output": result,
                "error": None
            }
        except Exception as e:
            logger.error(f"Code execution failed: {str(e)}")
            return {
                "success": False,
                "output": None,
                "error": str(e)
            }
    
    @staticmethod
    async def verify_syntax(code: str) -> Dict[str, Any]:
        """
        Verify Python code syntax
        
        Args:
            code: Python code to check
            
        Returns:
            Verification result
        """
        try:
            compile(code, '<string>', 'exec')
            return {
                "valid": True,
                "error": None
            }
        except SyntaxError as e:
            return {
                "valid": False,
                "error": str(e)
            }
