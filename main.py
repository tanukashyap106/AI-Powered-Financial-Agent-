import os
import sys
import importlib.util

# Load code/main.py explicitly to avoid standard library 'code' module conflict
root_dir = os.path.dirname(os.path.abspath(__file__))
code_dir = os.path.join(root_dir, "code")

if code_dir not in sys.path:
    sys.path.insert(0, code_dir)

main_py_path = os.path.join(code_dir, "main.py")
spec = importlib.util.spec_from_file_location("financial_agent_main", main_py_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

if __name__ == "__main__":
    module.run_pipeline()
