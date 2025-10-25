#!/usr/bin/env python3
"""
Analizador Específico para COMAU-VISION
======================================

Analizador enfocado en el código real del proyecto, excluyendo archivos de análisis.
"""

import os
import re
import json
import ast
from pathlib import Path
from typing import Dict, List, Set, Optional
from dataclasses import dataclass, asdict
from collections import defaultdict

@dataclass
class FunctionInfo:
    id: str
    name: str
    file_path: str
    line_start: int
    line_end: int
    is_entry_point: bool = False
    is_exported: bool = False
    calls: Set[str] = None
    called_by: Set[str] = None
    complexity: int = 0
    
    def __post_init__(self):
        if self.calls is None:
            self.calls = set()
        if self.called_by is None:
            self.called_by = set()

class TargetedAnalyzer:
    """Analizador específico para el código del proyecto"""
    
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.functions: Dict[str, FunctionInfo] = {}
        
        # Archivos a excluir del análisis
        self.exclude_files = {
            'code_analyzer.py',
            'dead_code_eliminator.py', 
            'targeted_analyzer.py',
            'auto_cleanup.py'
        }
        
        # Patrones de puntos de entrada específicos del proyecto
        self.entry_patterns = [
            r'@app\.route\s*\(',           # Flask routes
            r'def\s+main\s*\(',            # Función main
            r'if\s+__name__\s*==\s*["\']__main__["\']',  # Script principal
            r'def\s+api_',                 # API endpoints
            r'def\s+video_feed',           # Video feed
        ]
    
    def analyze_project(self) -> Dict:
        """Análisis específico del proyecto"""
        print("🔍 Analizando código específico de COMAU-VISION...")
        
        # Encontrar archivos Python del proyecto
        python_files = self._find_project_files()
        print(f"📁 Archivos del proyecto: {len(python_files)}")
        
        # Analizar cada archivo
        for file_path in python_files:
            self._analyze_file(file_path)
        
        # Mapear dependencias
        self._map_dependencies()
        
        # Identificar funciones huérfanas
        orphaned = self._find_orphaned_functions()
        
        # Generar reporte
        report = self._generate_report(orphaned)
        
        return report
    
    def _find_project_files(self) -> List[Path]:
        """Encuentra archivos Python del proyecto (excluyendo archivos de análisis)"""
        python_files = []
        
        exclude_dirs = {'__pycache__', '.git', 'node_modules', 'venv', 'env'}
        
        for root, dirs, files in os.walk(self.project_root):
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            
            for file in files:
                if (file.endswith('.py') and 
                    file not in self.exclude_files and
                    not file.startswith('test_')):
                    python_files.append(Path(root) / file)
        
        return python_files
    
    def _analyze_file(self, file_path: Path):
        """Analiza un archivo específico"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parsear AST
            tree = ast.parse(content, filename=str(file_path))
            
            # Analizar funciones
            self._analyze_functions(tree, file_path, content)
            
        except Exception as e:
            print(f"⚠️ Error analizando {file_path}: {e}")
    
    def _analyze_functions(self, tree: ast.AST, file_path: Path, content: str):
        """Analiza funciones del archivo"""
        lines = content.split('\n')
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_id = f"{file_path.name}:{node.name}"
                
                # Detectar si es punto de entrada
                is_entry = self._is_entry_point(node, content, file_path.name)
                
                func_info = FunctionInfo(
                    id=func_id,
                    name=node.name,
                    file_path=str(file_path),
                    line_start=node.lineno,
                    line_end=node.end_lineno or node.lineno,
                    is_entry_point=is_entry,
                    is_exported=self._is_exported(node, content),
                    complexity=self._calculate_complexity(node)
                )
                
                # Analizar llamadas dentro de la función
                func_info.calls = self._find_function_calls(node)
                
                self.functions[func_id] = func_info
    
    def _is_entry_point(self, node: ast.AST, content: str, filename: str) -> bool:
        """Detecta si la función es punto de entrada"""
        func_name = node.name
        
        # Verificar patrones específicos
        for pattern in self.entry_patterns:
            if re.search(pattern, content, re.MULTILINE):
                return True
        
        # Verificar si es main
        if func_name == 'main':
            return True
        
        # Verificar si es función de Flask
        if func_name.startswith('api_') or func_name == 'video_feed':
            return True
        
        return False
    
    def _is_exported(self, node: ast.AST, content: str) -> bool:
        """Detecta si la función es exportada"""
        func_name = node.name
        
        # Buscar en __all__
        all_match = re.search(r'__all__\s*=\s*\[(.*?)\]', content, re.DOTALL)
        if all_match and func_name in all_match.group(1):
            return True
        
        return False
    
    def _calculate_complexity(self, node: ast.AST) -> int:
        """Calcula complejidad ciclomática"""
        complexity = 1
        
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.AsyncFor, 
                                ast.ExceptHandler, ast.With, ast.AsyncWith)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
        
        return complexity
    
    def _find_function_calls(self, node: ast.AST) -> Set[str]:
        """Encuentra llamadas a funciones"""
        calls = set()
        
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    calls.add(child.func.id)
                elif isinstance(child.func, ast.Attribute):
                    calls.add(child.func.attr)
        
        return calls
    
    def _map_dependencies(self):
        """Mapea dependencias entre funciones"""
        print("🔗 Mapeando dependencias...")
        
        for func_id, func_info in self.functions.items():
            # Crear copia para evitar modificar durante iteración
            calls_copy = func_info.calls.copy()
            for call_name in calls_copy:
                # Buscar la función llamada
                called_func = self._find_function_by_name(call_name, func_info.file_path)
                if called_func:
                    # Actualizar con ID completo
                    func_info.calls.remove(call_name)
                    func_info.calls.add(called_func.id)
                    self.functions[called_func.id].called_by.add(func_id)
    
    def _find_function_by_name(self, name: str, current_file: str) -> Optional[FunctionInfo]:
        """Busca función por nombre"""
        # Buscar en el mismo archivo
        for func_id, func_info in self.functions.items():
            if (func_info.name == name and 
                func_info.file_path == current_file):
                return func_info
        
        return None
    
    def _find_orphaned_functions(self) -> List[str]:
        """Encuentra funciones huérfanas"""
        orphaned = []
        
        for func_id, func_info in self.functions.items():
            # No es huérfana si:
            # 1. Es punto de entrada
            # 2. Es exportada
            # 3. Es llamada por otra función
            if (not func_info.is_entry_point and 
                not func_info.is_exported and 
                len(func_info.called_by) == 0):
                orphaned.append(func_id)
        
        return orphaned
    
    def _generate_report(self, orphaned_functions: List[str]) -> Dict:
        """Genera reporte del análisis"""
        report = {
            'summary': {
                'total_functions': len(self.functions),
                'entry_points': len([f for f in self.functions.values() if f.is_entry_point]),
                'exported_functions': len([f for f in self.functions.values() if f.is_exported]),
                'orphaned_functions': len(orphaned_functions),
                'complexity_avg': sum(f.complexity for f in self.functions.values()) / len(self.functions) if self.functions else 0
            },
            'functions': {func_id: asdict(func_info) for func_id, func_info in self.functions.items()},
            'orphaned_functions': orphaned_functions,
            'entry_points': [func_id for func_id, func_info in self.functions.items() if func_info.is_entry_point],
            'cleanup_suggestions': self._generate_cleanup_suggestions(orphaned_functions)
        }
        
        return report
    
    def _generate_cleanup_suggestions(self, orphaned_functions: List[str]) -> Dict:
        """Genera sugerencias de limpieza"""
        suggestions = {
            'safe_to_delete': [],
            'review_needed': []
        }
        
        for func_id in orphaned_functions:
            func_info = self.functions[func_id]
            
            if len(func_info.calls) == 0:
                suggestions['safe_to_delete'].append({
                    'function_id': func_id,
                    'function_name': func_info.name,
                    'file_path': func_info.file_path,
                    'lines': f"{func_info.line_start}-{func_info.line_end}",
                    'reason': 'Función huérfana sin dependencias internas'
                })
            else:
                suggestions['review_needed'].append({
                    'function_id': func_id,
                    'function_name': func_info.name,
                    'file_path': func_info.file_path,
                    'lines': f"{func_info.line_start}-{func_info.line_end}",
                    'reason': 'Función huérfana con dependencias internas',
                    'internal_calls': list(func_info.calls)
                })
        
        return suggestions

def main():
    """Función principal"""
    analyzer = TargetedAnalyzer()
    report = analyzer.analyze_project()
    
    # Guardar reporte
    with open('targeted_analysis_report.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    
    # Mostrar resumen
    print("\n" + "="*60)
    print("📊 ANÁLISIS ESPECÍFICO DE COMAU-VISION")
    print("="*60)
    print(f"🔧 Funciones encontradas: {report['summary']['total_functions']}")
    print(f"🚪 Puntos de entrada: {report['summary']['entry_points']}")
    print(f"📤 Funciones exportadas: {report['summary']['exported_functions']}")
    print(f"💀 Funciones huérfanas: {report['summary']['orphaned_functions']}")
    print(f"📈 Complejidad promedio: {report['summary']['complexity_avg']:.2f}")
    
    print(f"\n🗑️ FUNCIONES SEGURAS PARA ELIMINAR: {len(report['cleanup_suggestions']['safe_to_delete'])}")
    for item in report['cleanup_suggestions']['safe_to_delete']:
        print(f"  - {item['function_name']} ({item['file_path']}:{item['lines']})")
    
    print(f"\n⚠️ FUNCIONES QUE NECESITAN REVISIÓN: {len(report['cleanup_suggestions']['review_needed'])}")
    for item in report['cleanup_suggestions']['review_needed']:
        print(f"  - {item['function_name']} ({item['file_path']}:{item['lines']})")
        print(f"    Llamadas internas: {', '.join(item['internal_calls'])}")
    
    print(f"\n📄 Reporte completo guardado en: targeted_analysis_report.json")

if __name__ == "__main__":
    main()
