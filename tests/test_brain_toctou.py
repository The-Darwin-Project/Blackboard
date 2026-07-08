import ast
from pathlib import Path

def test_run_agent_task_release_task_state_ordering():
    """
    Verify that _release_task_state is called BEFORE mark_turn_status and stamp_event
    in _run_agent_task to prevent TOCTOU races with is_intermediate.
    """
    brain_path = Path("src/agents/brain.py")
    if not brain_path.exists():
        brain_path = Path("BlackBoard/src/agents/brain.py")
        
    with open(brain_path, "r") as f:
        tree = ast.parse(f.read())
        
    class RunAgentTaskVisitor(ast.NodeVisitor):
        def __init__(self):
            self.in_run_agent_task = False
            self.append_calls = []
            self.release_calls = []
            self.mark_calls = []
            self.stamp_calls = []
            
        def visit_AsyncFunctionDef(self, node):
            if node.name == "_run_agent_task":
                self.in_run_agent_task = True
                self.generic_visit(node)
                self.in_run_agent_task = False
            else:
                self.generic_visit(node)
                
        def visit_Call(self, node):
            if self.in_run_agent_task:
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr == "_append_and_broadcast":
                        self.append_calls.append(node.lineno)
                    elif node.func.attr == "_release_task_state":
                        self.release_calls.append(node.lineno)
                    elif node.func.attr == "mark_turn_status":
                        self.mark_calls.append(node.lineno)
                    elif node.func.attr == "stamp_event":
                        self.stamp_calls.append(node.lineno)
            self.generic_visit(node)
            
    visitor = RunAgentTaskVisitor()
    visitor.visit(tree)
    
    assert visitor.append_calls, "Expected _append_and_broadcast calls"
    assert visitor.release_calls, "Expected _release_task_state calls"
    
    # In success path, _append_and_broadcast is around line 3331
    # We want to ensure that _release_task_state is called immediately after it,
    # and BEFORE mark_turn_status and stamp_event.
    
    # Let's find the first append call in the main try block (success path)
    # and the corresponding release call.
    # The success path append is typically the first one.
    success_append_line = visitor.append_calls[0]
    
    # Find the release call that comes after this append
    success_release_line = next(line for line in visitor.release_calls if line > success_append_line)
    
    # Find mark_turn_status and stamp_event that come after this append
    success_mark_lines = [line for line in visitor.mark_calls if line > success_append_line]
    success_stamp_lines = [line for line in visitor.stamp_calls if line > success_append_line]
    
    if success_mark_lines:
        assert success_release_line < success_mark_lines[0], \
            f"_release_task_state (line {success_release_line}) must be called BEFORE mark_turn_status (line {success_mark_lines[0]})"
            
    if success_stamp_lines:
        assert success_release_line < success_stamp_lines[0], \
            f"_release_task_state (line {success_release_line}) must be called BEFORE stamp_event (line {success_stamp_lines[0]})"

def test_handle_wake_task_release_task_state_ordering():
    """
    Verify that _release_task_state is called BEFORE stamp_event
    in handle_wake_task to prevent TOCTOU races.
    """
    brain_path = Path("src/agents/brain.py")
    if not brain_path.exists():
        brain_path = Path("BlackBoard/src/agents/brain.py")
        
    with open(brain_path, "r") as f:
        tree = ast.parse(f.read())
        
    class HandleWakeTaskVisitor(ast.NodeVisitor):
        def __init__(self):
            self.in_handle_wake_task = False
            self.append_calls = []
            self.release_calls = []
            self.stamp_calls = []
            
        def visit_AsyncFunctionDef(self, node):
            if node.name == "handle_wake_task":
                self.in_handle_wake_task = True
                self.generic_visit(node)
                self.in_handle_wake_task = False
            else:
                self.generic_visit(node)
                
        def visit_Call(self, node):
            if self.in_handle_wake_task:
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr == "_append_and_broadcast":
                        self.append_calls.append(node.lineno)
                    elif node.func.attr == "_release_task_state":
                        self.release_calls.append(node.lineno)
                    elif node.func.attr == "stamp_event":
                        self.stamp_calls.append(node.lineno)
            self.generic_visit(node)
            
    visitor = HandleWakeTaskVisitor()
    visitor.visit(tree)
    
    # Find the success path append (the one before stamp_event)
    success_stamp_line = visitor.stamp_calls[0] if visitor.stamp_calls else None
    if success_stamp_line:
        # Find the append that precedes this stamp
        success_append_line = max(line for line in visitor.append_calls if line < success_stamp_line)
        # Find the release that comes after this append
        success_release_line = next(line for line in visitor.release_calls if line > success_append_line)
        
        assert success_release_line < success_stamp_line, \
            f"_release_task_state (line {success_release_line}) must be called BEFORE stamp_event (line {success_stamp_line})"
