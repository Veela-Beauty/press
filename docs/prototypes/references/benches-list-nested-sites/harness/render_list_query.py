"""Render ReleaseGroup.get_list_query (the real function body, extracted by AST) to MariaDB SQL via pypika."""
import ast
import sys
import types

from pypika import MySQLQuery, Table
from pypika import functions as fn

src = open(sys.argv[1]).read()
cls = next(n for n in ast.parse(src).body if isinstance(n, ast.ClassDef) and n.name == "ReleaseGroup")
func = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "get_list_query")
func.decorator_list = []


class DocType(Table):
	def __init__(self, name):
		super().__init__(f"tab{name}")


qb = types.SimpleNamespace(DocType=DocType, from_=MySQLQuery.from_)
frappe = types.SimpleNamespace(
	qb=qb,
	query_builder=types.SimpleNamespace(functions=types.SimpleNamespace(Count=fn.Count)),
	local=types.SimpleNamespace(team=lambda: types.SimpleNamespace(name="team-1")),
)
ns = {"frappe": frappe}
exec(compile(ast.fix_missing_locations(ast.Module(body=[func], type_ignores=[])), "release_group.py", "exec"), ns)

RG = DocType("Release Group")
base = MySQLQuery.from_(RG).select(RG.name, RG.title)
filters = {"server": sys.argv[2]} if len(sys.argv) > 2 else {}
print(ns["get_list_query"](base, filters).get_sql() + ";")
