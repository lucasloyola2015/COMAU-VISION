#!/usr/bin/env python3
"""
COMAU-VISION Code Analyzer
=========================

Scanner estático completo que:
1. Mapea TODAS las funciones del proyecto
2. Analiza dependencias (quién llama a quién)
3. Identifica código huérfano
4. Propone eliminación en cascada
5. Genera reporte de limpieza

Uso: python code_analyzer.py
"""

import os
import re
import json
import ast
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass, asdict
from collections import defaultdict, Counter

@dataclass
class FunctionInfo:
    """Información completa de una función"""
    id: str
    name: str
    file_path: str
    line_start: int
    line_end: int
    is_method: bool = False
    is_async: bool = False
    parameters: List[str] = None
    return_type: Optional[str] = None
    docstring: Optional[str] = None
    complexity: int = 0
    calls: Set[str] = None  # IDs de funciones que llama
    called_by: Set[str] = None  # IDs de funciones que la llaman
    is_exported: bool = False  # Si es parte de la API pública
    is_entry_point: bool = False  # Si es punto de entrada (main, route handlers)
    
    def __post_init__(self):
        if self.calls is None:
            self.calls = set()
        if self.called_by is None:
            self.called_by = set()
        if self.parameters is None:
            self.parameters = []

class CodeAnalyzer:
    """Analizador estático completo del código"""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.functions: Dict[str, FunctionInfo] = {}
        self.files_analyzed: Set[str] = set()
        self.imports_map: Dict[str, Set[str]] = defaultdict(set)
        self.entry_points: Set[str] = set()
        
        # Patrones para identificar puntos de entrada
        self.entry_patterns = [
            r'@app\.route\s*\(',  # Flask routes
            r'def\s+main\s*\(',   # Función main
            r'if\s+__name__\s*==\s*["\']__main__["\']',  # Script principal
            r'def\s+test_',       # Funciones de test
            r'def\s+setup_',     # Funciones de setup
            r'def\s+init_',      # Funciones de inicialización
        ]
        
        # Patrones para identificar funciones exportadas
        self.export_patterns = [
            r'__all__\s*=',       # Lista __all__
            r'export\s+',        # Palabra export
            r'public\s+',        # Palabra public
        ]
    
    def analyze_project(self) -> Dict:
        """Análisis completo del proyecto"""
        print("🔍 Iniciando análisis estático completo...")
        
        # 1. Escanear todos los archivos Python
        python_files = self._find_python_files()
        print(f"📁 Encontrados {len(python_files)} archivos Python")
        
        # 2. Analizar cada archivo
        for file_path in python_files:
            self._analyze_file(file_path)
        
        # 3. Mapear dependencias
        self._map_dependencies()
        
        # 4. Identificar puntos de entrada
        self._identify_entry_points()
        
        # 5. Identificar código huérfano
        orphaned_functions = self._find_orphaned_functions()
        
        # 6. Generar reporte
        report = self._generate_report(orphaned_functions)
        
        return report
    
    def _find_python_files(self) -> List[Path]:
        """Encuentra todos los archivos Python del proyecto"""
        python_files = []
        
        # Excluir directorios comunes
        exclude_dirs = {'__pycache__', '.git', 'node_modules', 'venv', 'env'}
        
        for root, dirs, files in os.walk(self.project_root):
            # Filtrar directorios excluidos
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            
            for file in files:
                if file.endswith('.py'):
                    python_files.append(Path(root) / file)
        
        return python_files
    
    def _analyze_file(self, file_path: Path):
        """Analiza un archivo Python completo"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parsear AST
            tree = ast.parse(content, filename=str(file_path))
            
            # Analizar imports
            self._analyze_imports(tree, file_path)
            
            # Analizar funciones
            self._analyze_functions(tree, file_path, content)
            
            self.files_analyzed.add(str(file_path))
            
        except Exception as e:
            print(f"⚠️ Error analizando {file_path}: {e}")
    
    def _analyze_imports(self, tree: ast.AST, file_path: Path):
        """Analiza imports del archivo"""
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.imports_map[str(file_path)].add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    self.imports_map[str(file_path)].add(node.module)
    
    def _analyze_functions(self, tree: ast.AST, file_path: Path, content: str):
        """Analiza todas las funciones del archivo"""
        lines = content.split('\n')
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_id = f"{file_path.name}:{node.name}"
                
                # Extraer información de la función
                func_info = FunctionInfo(
                    id=func_id,
                    name=node.name,
                    file_path=str(file_path),
                    line_start=node.lineno,
                    line_end=node.end_lineno or node.lineno,
                    is_method=isinstance(node, ast.FunctionDef) and 
                             any(isinstance(parent, ast.ClassDef) for parent in ast.walk(tree) 
                                 if hasattr(parent, 'lineno') and parent.lineno < node.lineno),
                    is_async=isinstance(node, ast.AsyncFunctionDef),
                    parameters=[arg.arg for arg in node.args.args],
                    docstring=ast.get_docstring(node),
                    complexity=self._calculate_complexity(node)
                )
                
                # Detectar si es punto de entrada
                func_info.is_entry_point = self._is_entry_point(node, content)
                func_info.is_exported = self._is_exported(node, content)
                
                # Analizar llamadas dentro de la función
                func_info.calls = self._find_function_calls(node)
                
                self.functions[func_id] = func_info
    
    def _calculate_complexity(self, node: ast.AST) -> int:
        """Calcula complejidad ciclomática de la función"""
        complexity = 1  # Base complexity
        
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.AsyncFor, 
                                ast.ExceptHandler, ast.With, ast.AsyncWith)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
        
        return complexity
    
    def _is_entry_point(self, node: ast.AST, content: str) -> bool:
        """Detecta si la función es un punto de entrada"""
        func_name = node.name
        
        # Verificar patrones de entrada
        for pattern in self.entry_patterns:
            if re.search(pattern, content, re.MULTILINE):
                return True
        
        # Verificar si es main
        if func_name == 'main':
            return True
        
        return False
    
    def _is_exported(self, node: ast.AST, content: str) -> bool:
        """Detecta si la función es exportada públicamente"""
        func_name = node.name
        
        # Buscar en __all__
        all_match = re.search(r'__all__\s*=\s*\[(.*?)\]', content, re.DOTALL)
        if all_match and func_name in all_match.group(1):
            return True
        
        # Buscar patrones de exportación
        for pattern in self.export_patterns:
            if re.search(pattern, content, re.MULTILINE):
                return True
        
        return False
    
    def _find_function_calls(self, node: ast.AST) -> Set[str]:
        """Encuentra todas las llamadas a funciones dentro del nodo"""
        calls = set()
        
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    calls.add(child.func.id)
                elif isinstance(child.func, ast.Attribute):
                    # Para métodos como obj.method()
                    calls.add(child.func.attr)
        
        return calls
    
    def _map_dependencies(self):
        """Mapea dependencias entre funciones"""
        print("🔗 Mapeando dependencias...")
        
        for func_id, func_info in self.functions.items():
            # Crear copia de las llamadas para evitar modificar durante iteración
            calls_copy = func_info.calls.copy()
            for call_name in calls_copy:
                # Buscar la función llamada
                called_func = self._find_function_by_name(call_name, func_info.file_path)
                if called_func:
                    # Actualizar las llamadas con el ID completo
                    func_info.calls.remove(call_name)
                    func_info.calls.add(called_func.id)
                    self.functions[called_func.id].called_by.add(func_id)
    
    def _find_function_by_name(self, name: str, current_file: str) -> Optional[FunctionInfo]:
        """Busca una función por nombre en el archivo actual y imports"""
        # Buscar en el mismo archivo
        for func_id, func_info in self.functions.items():
            if (func_info.name == name and 
                func_info.file_path == current_file):
                return func_info
        
        # TODO: Implementar búsqueda en imports
        return None
    
    def _identify_entry_points(self):
        """Identifica puntos de entrada del sistema"""
        for func_id, func_info in self.functions.items():
            if func_info.is_entry_point:
                self.entry_points.add(func_id)
    
    def _find_orphaned_functions(self) -> List[str]:
        """Encuentra funciones huérfanas (no llamadas nunca)"""
        orphaned = []
        
        for func_id, func_info in self.functions.items():
            # No es huérfana si:
            # 1. Es punto de entrada
            # 2. Es exportada públicamente
            # 3. Es llamada por otra función
            if (not func_info.is_entry_point and 
                not func_info.is_exported and 
                len(func_info.called_by) == 0):
                orphaned.append(func_id)
        
        return orphaned
    
    def _generate_report(self, orphaned_functions: List[str]) -> Dict:
        """Genera reporte completo del análisis"""
        report = {
            'summary': {
                'total_files': len(self.files_analyzed),
                'total_functions': len(self.functions),
                'entry_points': len(self.entry_points),
                'orphaned_functions': len(orphaned_functions),
                'complexity_avg': sum(f.complexity for f in self.functions.values()) / len(self.functions) if self.functions else 0
            },
            'functions': {func_id: asdict(func_info) for func_id, func_info in self.functions.items()},
            'orphaned_functions': orphaned_functions,
            'entry_points': list(self.entry_points),
            'cleanup_suggestions': self._generate_cleanup_suggestions(orphaned_functions)
        }
        
        return report
    
    def _generate_cleanup_suggestions(self, orphaned_functions: List[str]) -> Dict:
        """Genera sugerencias de limpieza"""
        suggestions = {
            'safe_to_delete': [],
            'cascade_deletion': [],
            'review_needed': []
        }
        
        for func_id in orphaned_functions:
            func_info = self.functions[func_id]
            
            # Si la función no llama a otras funciones, es segura de eliminar
            if len(func_info.calls) == 0:
                suggestions['safe_to_delete'].append({
                    'function_id': func_id,
                    'reason': 'Función huérfana sin dependencias',
                    'file': func_info.file_path,
                    'lines': f"{func_info.line_start}-{func_info.line_end}"
                })
            else:
                # Necesita revisión manual
                suggestions['review_needed'].append({
                    'function_id': func_id,
                    'reason': 'Función huérfana con dependencias internas',
                    'calls': list(func_info.calls),
                    'file': func_info.file_path,
                    'lines': f"{func_info.line_start}-{func_info.line_end}"
                })
        
        return suggestions

def main():
    """Función principal del analizador"""
    project_root = "."  # Directorio actual
    
    analyzer = CodeAnalyzer(project_root)
    report = analyzer.analyze_project()
    
    # Guardar reporte
    with open('code_analysis_report.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    
    # Mostrar resumen
    print("\n" + "="*60)
    print("📊 REPORTE DE ANÁLISIS ESTÁTICO")
    print("="*60)
    print(f"📁 Archivos analizados: {report['summary']['total_files']}")
    print(f"🔧 Funciones encontradas: {report['summary']['total_functions']}")
    print(f"🚪 Puntos de entrada: {report['summary']['entry_points']}")
    print(f"💀 Funciones huérfanas: {report['summary']['orphaned_functions']}")
    print(f"📈 Complejidad promedio: {report['summary']['complexity_avg']:.2f}")
    
    print(f"\n🗑️ FUNCIONES SEGURAS PARA ELIMINAR: {len(report['cleanup_suggestions']['safe_to_delete'])}")
    for item in report['cleanup_suggestions']['safe_to_delete']:
        print(f"  - {item['function_id']} ({item['file']}:{item['lines']})")
    
    print(f"\n⚠️ FUNCIONES QUE NECESITAN REVISIÓN: {len(report['cleanup_suggestions']['review_needed'])}")
    for item in report['cleanup_suggestions']['review_needed']:
        print(f"  - {item['function_id']} ({item['file']}:{item['lines']})")
        print(f"    Llamadas internas: {', '.join(item['calls'])}")
    
    print(f"\n📄 Reporte completo guardado en: code_analysis_report.json")

if __name__ == "__main__":
    main()
