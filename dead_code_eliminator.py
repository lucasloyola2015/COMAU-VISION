#!/usr/bin/env python3
"""
COMAU-VISION Dead Code Eliminator
=================================

Algoritmo de eliminación en cascada que:
1. Identifica funciones huérfanas
2. Elimina funciones que solo son llamadas por funciones huérfanas
3. Continúa hasta que no hay más eliminaciones posibles
4. Genera reporte de limpieza automática

Uso: python dead_code_eliminator.py
"""

import json
import os
from typing import Dict, List, Set, Tuple
from dataclasses import dataclass
from collections import defaultdict

@dataclass
class EliminationCandidate:
    """Candidato para eliminación"""
    function_id: str
    file_path: str
    function_name: str
    lines: str
    reason: str
    dependencies: List[str]  # Funciones que esta función llama
    dependents: List[str]      # Funciones que llaman a esta función
    safe_to_delete: bool
    cascade_level: int = 0

class DeadCodeEliminator:
    """Eliminador de código muerto con análisis en cascada"""
    
    def __init__(self, analysis_report_path: str = "code_analysis_report.json"):
        self.analysis_report_path = analysis_report_path
        self.report = None
        self.functions = {}
        self.entry_points = set()
        self.elimination_candidates = []
        self.elimination_order = []
        
    def load_analysis_report(self):
        """Carga el reporte de análisis estático"""
        try:
            with open(self.analysis_report_path, 'r', encoding='utf-8') as f:
                self.report = json.load(f)
            
            self.functions = self.report['functions']
            self.entry_points = set(self.report['entry_points'])
            
            print(f"✅ Reporte cargado: {len(self.functions)} funciones, {len(self.entry_points)} puntos de entrada")
            
        except FileNotFoundError:
            print(f"❌ Error: No se encontró el archivo {self.analysis_report_path}")
            print("   Ejecuta primero: python code_analyzer.py")
            return False
        
        return True
    
    def analyze_elimination_candidates(self) -> List[EliminationCandidate]:
        """Analiza candidatos para eliminación con análisis en cascada"""
        print("\n🔍 Analizando candidatos para eliminación...")
        
        candidates = []
        
        # Nivel 1: Funciones huérfanas directas
        level_1_candidates = self._find_direct_orphans()
        candidates.extend(level_1_candidates)
        
        # Niveles 2+: Análisis en cascada
        current_level = 2
        while True:
            next_level_candidates = self._find_cascade_candidates(candidates, current_level)
            if not next_level_candidates:
                break
            candidates.extend(next_level_candidates)
            current_level += 1
        
        # Ordenar por nivel de cascada y seguridad
        candidates.sort(key=lambda x: (x.cascade_level, not x.safe_to_delete))
        
        self.elimination_candidates = candidates
        return candidates
    
    def _find_direct_orphans(self) -> List[EliminationCandidate]:
        """Encuentra funciones huérfanas directas (nivel 1)"""
        candidates = []
        
        for func_id, func_info in self.functions.items():
            # Saltar si es punto de entrada
            if func_id in self.entry_points:
                continue
            
            # Verificar si es huérfana (no llamada por nadie)
            called_by = func_info.get('called_by', [])
            if len(called_by) == 0:
                candidate = EliminationCandidate(
                    function_id=func_id,
                    file_path=func_info['file_path'],
                    function_name=func_info['name'],
                    lines=f"{func_info['line_start']}-{func_info['line_end']}",
                    reason="Función huérfana directa",
                    dependencies=func_info.get('calls', []),
                    dependents=called_by,
                    safe_to_delete=len(func_info.get('calls', [])) == 0,
                    cascade_level=1
                )
                candidates.append(candidate)
        
        return candidates
    
    def _find_cascade_candidates(self, existing_candidates: List[EliminationCandidate], level: int) -> List[EliminationCandidate]:
        """Encuentra candidatos de cascada (funciones que solo son llamadas por funciones ya marcadas para eliminación)"""
        candidates = []
        
        # Crear set de funciones ya marcadas para eliminación
        marked_for_deletion = {c.function_id for c in existing_candidates}
        
        for func_id, func_info in self.functions.items():
            # Saltar si ya está marcada para eliminación
            if func_id in marked_for_deletion:
                continue
            
            # Saltar si es punto de entrada
            if func_id in self.entry_points:
                continue
            
            # Verificar si solo es llamada por funciones marcadas para eliminación
            called_by = func_info.get('called_by', [])
            if called_by and all(caller in marked_for_deletion for caller in called_by):
                candidate = EliminationCandidate(
                    function_id=func_id,
                    file_path=func_info['file_path'],
                    function_name=func_info['name'],
                    lines=f"{func_info['line_start']}-{func_info['line_end']}",
                    reason=f"Función huérfana de cascada (nivel {level})",
                    dependencies=func_info.get('calls', []),
                    dependents=called_by,
                    safe_to_delete=len(func_info.get('calls', [])) == 0,
                    cascade_level=level
                )
                candidates.append(candidate)
        
        return candidates
    
    def generate_elimination_plan(self) -> Dict:
        """Genera plan de eliminación detallado"""
        print("\n📋 Generando plan de eliminación...")
        
        plan = {
            'summary': {
                'total_candidates': len(self.elimination_candidates),
                'safe_to_delete': len([c for c in self.elimination_candidates if c.safe_to_delete]),
                'need_review': len([c for c in self.elimination_candidates if not c.safe_to_delete]),
                'max_cascade_level': max([c.cascade_level for c in self.elimination_candidates]) if self.elimination_candidates else 0
            },
            'elimination_order': [],
            'files_affected': set(),
            'functions_by_level': defaultdict(list)
        }
        
        # Agrupar por nivel de cascada
        for candidate in self.elimination_candidates:
            plan['functions_by_level'][candidate.cascade_level].append(candidate)
            plan['files_affected'].add(candidate.file_path)
            
            plan['elimination_order'].append({
                'function_id': candidate.function_id,
                'file_path': candidate.file_path,
                'function_name': candidate.function_name,
                'lines': candidate.lines,
                'reason': candidate.reason,
                'safe_to_delete': candidate.safe_to_delete,
                'cascade_level': candidate.cascade_level,
                'dependencies_count': len(candidate.dependencies),
                'dependents_count': len(candidate.dependents)
            })
        
        plan['files_affected'] = list(plan['files_affected'])
        
        return plan
    
    def generate_cleanup_script(self, plan: Dict) -> str:
        """Genera script de limpieza automática"""
        script_content = '''#!/usr/bin/env python3
"""
Script de limpieza automática generado por Dead Code Eliminator
================================================================

Este script elimina automáticamente las funciones identificadas como código muerto.
EJECUTAR CON PRECAUCIÓN - HACER BACKUP ANTES DE EJECUTAR
"""

import os
import re
from pathlib import Path

def delete_function_from_file(file_path: str, function_name: str, lines: str):
    """Elimina una función específica de un archivo"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        lines_list = content.split('\\n')
        start_line, end_line = map(int, lines.split('-'))
        
        # Eliminar líneas (índices basados en 0)
        new_lines = lines_list[:start_line-1] + lines_list[end_line:]
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write('\\n'.join(new_lines))
        
        print(f"✅ Eliminada función {function_name} de {file_path} (líneas {lines})")
        return True
        
    except Exception as e:
        print(f"❌ Error eliminando {function_name} de {file_path}: {e}")
        return False

def main():
    """Función principal de limpieza"""
    print("🧹 Iniciando limpieza automática de código muerto...")
    
    # Lista de eliminaciones (generada automáticamente)
    eliminations = [
'''
        
        # Agregar eliminaciones al script
        for item in plan['elimination_order']:
            if item['safe_to_delete']:
                script_content += f'''        ("{item['file_path']}", "{item['function_name']}", "{item['lines']}"),\n'''
        
        script_content += '''    ]
    
    success_count = 0
    total_count = len(eliminations)
    
    for file_path, function_name, lines in eliminations:
        if delete_function_from_file(file_path, function_name, lines):
            success_count += 1
    
    print(f"\\n📊 Resumen de limpieza:")
    print(f"   ✅ Funciones eliminadas: {success_count}/{total_count}")
    print(f"   📁 Archivos modificados: {len(set(item[0] for item in eliminations))}")

if __name__ == "__main__":
    main()
'''
        
        return script_content
    
    def save_elimination_plan(self, plan: Dict, output_file: str = "elimination_plan.json"):
        """Guarda el plan de eliminación en archivo JSON"""
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(plan, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"📄 Plan de eliminación guardado en: {output_file}")
    
    def save_cleanup_script(self, script_content: str, output_file: str = "auto_cleanup.py"):
        """Guarda el script de limpieza automática"""
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(script_content)
        
        print(f"🧹 Script de limpieza guardado en: {output_file}")
    
    def run_analysis(self):
        """Ejecuta análisis completo de eliminación"""
        print("🔍 COMAU-VISION Dead Code Eliminator")
        print("=" * 50)
        
        # Cargar reporte de análisis
        if not self.load_analysis_report():
            return
        
        # Analizar candidatos
        candidates = self.analyze_elimination_candidates()
        
        # Generar plan
        plan = self.generate_elimination_plan()
        
        # Guardar resultados
        self.save_elimination_plan(plan)
        
        # Generar script de limpieza
        script_content = self.generate_cleanup_script(plan)
        self.save_cleanup_script(script_content)
        
        # Mostrar resumen
        self._print_summary(plan)
    
    def _print_summary(self, plan: Dict):
        """Imprime resumen del análisis"""
        print("\n" + "="*60)
        print("📊 RESUMEN DE ELIMINACIÓN DE CÓDIGO MUERTO")
        print("="*60)
        
        summary = plan['summary']
        print(f"🔧 Total de candidatos: {summary['total_candidates']}")
        print(f"✅ Seguros para eliminar: {summary['safe_to_delete']}")
        print(f"⚠️ Necesitan revisión: {summary['need_review']}")
        print(f"📈 Nivel máximo de cascada: {summary['max_cascade_level']}")
        print(f"📁 Archivos afectados: {len(plan['files_affected'])}")
        
        print(f"\n🗑️ ELIMINACIONES POR NIVEL:")
        for level, functions in plan['functions_by_level'].items():
            safe_count = len([f for f in functions if f.safe_to_delete])
            review_count = len([f for f in functions if not f.safe_to_delete])
            print(f"   Nivel {level}: {len(functions)} funciones ({safe_count} seguras, {review_count} revisar)")
        
        print(f"\n📁 ARCHIVOS AFECTADOS:")
        for file_path in sorted(plan['files_affected']):
            file_candidates = [c for c in self.elimination_candidates if c.file_path == file_path]
            print(f"   {file_path}: {len(file_candidates)} funciones")
        
        print(f"\n🚀 PRÓXIMOS PASOS:")
        print(f"   1. Revisar elimination_plan.json para detalles")
        print(f"   2. HACER BACKUP del proyecto")
        print(f"   3. Ejecutar: python auto_cleanup.py")
        print(f"   4. Verificar que el sistema sigue funcionando")

def main():
    """Función principal"""
    eliminator = DeadCodeEliminator()
    eliminator.run_analysis()

if __name__ == "__main__":
    main()
