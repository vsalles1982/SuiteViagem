import copy
from pathlib import Path
import sqlite3
import tempfile
import unittest
from suiteviagem.core.models import money, new_query, validate
from suiteviagem.demo import run
from suiteviagem.history import History

class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'history.sqlite3'
    def tearDown(self):
        self.temp.cleanup()
    def test_money_exact_and_invalid(self):
        self.assertEqual(money('189.67'), 18967)
        self.assertEqual(money('0'), 0)
        for value in (1.2, True, '-1', 'NaN', 'Infinity', '1.001'):
            with self.assertRaises(ValueError):
                money(value)
    def test_roundtrip_all_modules_and_backup(self):
        with History(self.path) as history:
            ids = run(history)
            expected = [history.get(i) for i in ids]
            backup = Path(self.temp.name) / 'backup.sqlite3'
            history.backup(backup)
        with History(self.path) as reopened, History(backup) as restored:
            self.assertEqual(len(reopened.list()), 4)
            self.assertEqual([restored.get(i) for i in ids], expected)
            for query in expected:
                self.assertEqual(reopened.get(query['query_id']), query)
                self.assertEqual(query['results'][0]['price']['amount_minor'], 12345)
                self.assertIsNone(query['results'][0]['price']['total_minor'])
    def test_tax_arithmetic_and_unknown(self):
        with History(self.path) as history:
            query = history.get(run(history)[1])
        price = query['results'][0]['price']
        price.update(taxes_status='added', additional_taxes_minor=155, total_minor=12500)
        validate(query)
        price['total_minor'] = 12501
        with self.assertRaises(ValueError): validate(query)
        price.update(taxes_status='included', additional_taxes_minor=0, total_minor=12345)
        validate(query)
        price['taxes_status'] = 'unknown'
        with self.assertRaises(ValueError): validate(query)
    def test_empty_failed_cancelled_and_recovery(self):
        with History(self.path) as history:
            for status in ('succeeded', 'failed', 'cancelled'):
                query = new_query('events', {})
                history.create(query)
                history.start(query['query_id'])
                history.finish(query['query_id'], status=status, results=[], coverage=query['coverage'])
            pending = new_query('cars', {})
            history.create(pending)
            history.start(pending['query_id'])
        with History(self.path) as history:
            self.assertEqual(history.recover_interrupted(), 1)
            self.assertEqual(history.get(pending['query_id'])['status'], 'interrupted')
            self.assertEqual(len(history.list()), 4)
    def test_final_immutable_and_repeat(self):
        with History(self.path) as history:
            query = history.get(run(history)[0])
            with self.assertRaises(ValueError):
                history.finish(query['query_id'], status='failed', results=[], coverage=query['coverage'])
            self.assertEqual(history.get(query['query_id']), query)
            repeated = new_query('flights', query['requested'], query['query_id'])
            history.create(repeated)
            self.assertNotEqual(repeated['query_id'], query['query_id'])
    def test_invalid_result_rolls_back(self):
        with History(self.path) as history:
            original = history.get(run(history)[0])
            query = new_query('flights', {})
            history.create(query)
            history.start(query['query_id'])
            item = copy.deepcopy(original['results'][0])
            item['query_id'] = query['query_id']
            # UUID já existe em outra consulta: falha de banco não pode finalizar a nova.
            with self.assertRaises(sqlite3.IntegrityError):
                history.finish(query['query_id'], status='succeeded', results=[item], coverage=query['coverage'])
            self.assertEqual(history.get(query['query_id'])['status'], 'running')
            self.assertEqual(history.get(query['query_id'])['results'], [])
    def test_foreign_keys_and_future_schema(self):
        with History(self.path) as history:
            query = new_query('events', {}, '00000000-0000-4000-8000-000000000001')
            with self.assertRaises(sqlite3.IntegrityError): history.create(query)
            history.db.execute('INSERT INTO schema_migrations VALUES(2, ?)', ('future',))
            history.db.commit()
        with self.assertRaises(ValueError): History(self.path)

if __name__ == '__main__':
    unittest.main()
