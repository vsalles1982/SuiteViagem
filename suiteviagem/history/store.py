"""Histórico SQLite v1. Uma conexão por instância; transações curtas."""
import json
from pathlib import Path
import sqlite3
from suiteviagem.core.models import FINAL, check, now, validate

DDL = (
    'CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)',
    'CREATE TABLE queries(id TEXT PRIMARY KEY, parent_id TEXT REFERENCES queries(id), module TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, document TEXT NOT NULL)',
    'CREATE INDEX queries_module_date ON queries(module, created_at)',
    'CREATE TABLE results(id TEXT PRIMARY KEY, query_id TEXT NOT NULL REFERENCES queries(id), kind TEXT NOT NULL, title TEXT NOT NULL, currency TEXT, basis TEXT, amount_minor INTEGER, total_minor INTEGER, document TEXT NOT NULL)',
    'CREATE INDEX results_query ON results(query_id)',
    'CREATE TABLE query_events(id INTEGER PRIMARY KEY, query_id TEXT NOT NULL REFERENCES queries(id), occurred_at TEXT NOT NULL, phase TEXT NOT NULL, message TEXT NOT NULL)',
    'CREATE TABLE artifacts(id INTEGER PRIMARY KEY, query_id TEXT NOT NULL REFERENCES queries(id), kind TEXT NOT NULL, relative_path TEXT NOT NULL, size_bytes INTEGER NOT NULL, sha256 TEXT NOT NULL)',
)

def encode(document):
    return json.dumps(document, ensure_ascii=False, allow_nan=False)

class History:
    def __init__(self, path):
        if str(path) != ':memory:':
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=10)
        self.db.execute('PRAGMA foreign_keys=ON')
        try:
            self.db.execute('BEGIN IMMEDIATE')
            exists = self.db.execute("SELECT 1 FROM sqlite_master WHERE name='schema_migrations'").fetchone()
            if exists:
                versions = [r[0] for r in self.db.execute('SELECT version FROM schema_migrations ORDER BY version')]
                check(versions == [1], 'Versão de banco incompatível; não foi alterada.')
            else:
                for statement in DDL:
                    self.db.execute(statement)
                self.db.execute('INSERT INTO schema_migrations VALUES(1, ?)', (now(),))
            self.db.commit()
        except Exception:
            self.db.rollback()
            self.db.close()
            raise

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def create(self, query):
        validate(query)
        check(query['status'] == 'queued', 'Crie a consulta antes de executar.')
        with self.db:
            self.db.execute('INSERT INTO queries VALUES(?,?,?,?,?,?)',
                            (query['query_id'], query['parent_query_id'], query['module'], 'queued', query['created_at'], encode(query)))
            self._event(query['query_id'], 'queued', 'Consulta registrada')
        return query['query_id']

    def _event(self, query_id, phase, message):
        self.db.execute('INSERT INTO query_events(query_id,occurred_at,phase,message) VALUES(?,?,?,?)', (query_id, now(), phase, message))

    def get(self, query_id):
        row = self.db.execute('SELECT document FROM queries WHERE id=?', (query_id,)).fetchone()
        if row is None:
            raise KeyError('Consulta não encontrada')
        return json.loads(row[0])

    def _replace(self, query, expected):
        cursor = self.db.execute('UPDATE queries SET status=?, document=? WHERE id=? AND status=?',
                                 (query['status'], encode(query), query['query_id'], expected))
        check(cursor.rowcount == 1, 'Consulta mudou de estado; recarregue antes de continuar.')

    def start(self, query_id):
        with self.db:
            query = self.get(query_id)
            check(query['status'] == 'queued', 'Somente consulta em fila pode iniciar.')
            query.update(status='running', started_at=now())
            validate(query)
            self._replace(query, 'queued')
            self._event(query_id, 'running', 'Coleta iniciada')
        return query

    def finish(self, query_id, *, status, results, coverage, effective=None, errors=None, warnings=None, collector_version=None):
        check(status in FINAL, 'Estado final inválido.')
        with self.db:
            query = self.get(query_id)
            previous = query['status']
            check(previous == 'running' or previous == 'queued' and status == 'cancelled', 'Consulta concluída é imutável; repita para consultar novamente.')
            query.update(status=status, finished_at=now(), results=results, coverage=coverage,
                         effective=effective or {}, errors=errors or [], warnings=warnings or [], collector_version=collector_version)
            validate(query)
            for item in results:
                price = item['price'] or {}
                self.db.execute('INSERT INTO results VALUES(?,?,?,?,?,?,?,?,?)',
                                (item['result_id'], query_id, item['kind'], item['title'], price.get('currency'), price.get('basis'), price.get('amount_minor'), price.get('total_minor'), encode(item)))
            self._replace(query, previous)
            self._event(query_id, status, 'Consulta encerrada')
        return query

    def list(self, module=None, limit=20):
        check(type(limit) is int and 1 <= limit <= 1000, 'Limite entre 1 e 1000.')
        rows = self.db.execute('SELECT id,module,status,created_at FROM queries WHERE (? IS NULL OR module=?) ORDER BY created_at DESC,id DESC LIMIT ?', (module, module, limit))
        return [dict(zip(('query_id', 'module', 'status', 'created_at'), row)) for row in rows]

    def recover_interrupted(self):
        """Chamar somente no início do serviço, após confirmar ausência de worker ativo."""
        ids = [row[0] for row in self.db.execute("SELECT id FROM queries WHERE status='running'")]
        for query_id in ids:
            query = self.get(query_id)
            coverage = query['coverage']
            coverage.update(status='partial', stop_reason='process_interrupted')
            self.finish(query_id, status='interrupted', results=query['results'], coverage=coverage,
                        effective=query['effective'], errors=[{'code': 'interrupted', 'message': 'Execução interrompida antes da conclusão.'}])
        return len(ids)

    def backup(self, destination):
        path = Path(destination)
        with path.open('xb'):
            pass
        try:
            with sqlite3.connect(path) as target:
                self.db.backup(target)
        except Exception:
            path.unlink(missing_ok=True)
            raise
