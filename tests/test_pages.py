"""Completed templates are rendered only through the existing Bearer-token API."""
from contextlib import ExitStack, redirect_stdout
import io
import unittest
from unittest.mock import patch

from flask import template_rendered

from Backend import account, history, main
from tests.support.mock_supabase import MockDatabase
from tests.test_api import Assets


PAGE_URLS = {
    'member': ('/member', '/member.html'),
    'tasks': ('/tasks', '/task.html'),
    'history': ('/history', '/history.html'),
    'history-admin': ('/admin/history', '/history-admin', '/history-admin.html'),
    'admin': ('/admin',),
    'announcement': ('/announcements', '/announcement', '/announcement.html'),
    'member_donate': ('/member_donate', '/member_donate.html'),
    'account': ('/account', '/account.html'),
    'services': ('/services', '/services.html'),
    'faq': ('/faq', '/faq.html'),
}


class PageTests(unittest.TestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(redirect_stdout(io.StringIO()))
        stack.enter_context(patch('socket.socket.connect', side_effect=AssertionError('Network is forbidden')))
        stack.enter_context(patch.dict(main.app.config, TESTING=True))
        self.db = MockDatabase()
        for module in (account, history):
            stack.enter_context(patch.object(module, 'create_client', self.db.client))
        self.client = main.app.test_client()
        self.admin, self.alice, self.bob = self.db.fixture['accounts']

    def login(self, actor=None):
        actor = actor or self.alice
        response = self.client.post('/api/login', json={
            'email': actor['email'], 'password': actor['password'],
        })
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('Set-Cookie', response.headers)
        return {'Authorization': 'Bearer ' + response.json['access_token']}

    def rendered(self, page, headers, query=''):
        contexts = []

        def capture(sender, template, context, **extra):
            contexts.append(context)

        with template_rendered.connected_to(capture, main.app):
            response = self.client.get('/api/pages/' + page + query, headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json['ok'])
        self.assertEqual(len(contexts), 1)
        return response.json['html'], contexts[0]

    def add_bob_completion(self):
        self.db.tables['assignments'].append(self.db.defaults('assignments', {
            'task_id': self.db.fixture['tasks'][2]['id'], 'volunteer_id': self.bob['id'],
            'status': 'completed', 'reviewed_at': '2026-10-22T10:00:00+00:00',
        }))

    def test_page_urls_serve_only_a_neutral_loader_without_protected_content(self):
        with patch.object(main, 'Account') as account_factory, patch.object(main, 'History') as history_factory:
            for page, urls in PAGE_URLS.items():
                for url in urls:
                    with self.subTest(url=url):
                        response = self.client.get(url)
                        self.assertEqual(response.status_code, 200)
                        html = response.get_data(as_text=True)
                        self.assertIn(f'data-cic-page="{page}"', html)
                        self.assertIn('/static/js/pages.js', html)
                        self.assertLess(html.index('/static/js/api.js'), html.index('/static/js/pages.js'))
                        for private_text in ('Volunteer Dashboard', 'Volunteer History', 'Your Completed Tasks',
                                             'Available Tasks', '[MOCK CIC]', self.alice['email']):
                            self.assertNotIn(private_text, html)
                        parser = Assets()
                        parser.feed(html)
                        for asset in parser.urls:
                            with self.client.get(asset) as asset_response:
                                self.assertEqual(asset_response.status_code, 200, asset)
            account_factory.assert_not_called()
            history_factory.assert_not_called()

    def test_rendered_pages_require_bearer_token_before_client_construction(self):
        with patch.object(main, 'Account') as account_factory, patch.object(main, 'History') as history_factory:
            for page in PAGE_URLS:
                with self.subTest(page=page):
                    response = self.client.get('/api/pages/' + page)
                    self.assertEqual(response.status_code, 401)
                    self.assertFalse(response.json['ok'])
                    self.assertNotIn('html', response.json)
                    self.assertEqual(response.headers['Cache-Control'], 'no-store')
            account_factory.assert_not_called()
            history_factory.assert_not_called()

    def test_login_does_not_authorize_cookie_or_headerless_page_requests(self):
        self.login(self.admin)
        self.client.set_cookie('cic.page_token', self.db.token(self.admin['id']))
        for headers in ({}, {'Authorization': 'Basic credentials'}, {'Authorization': 'Bearer '}):
            response = self.client.get('/api/pages/history-admin', headers=headers)
            self.assertEqual(response.status_code, 401)
            self.assertNotIn('html', response.json)
        self.assertFalse(self.client.get('/api/me').json['logged_in'])

    def test_volunteer_can_load_completed_templates_and_all_local_assets(self):
        headers = self.login()
        for page in ('member', 'tasks', 'history', 'announcement', 'member_donate', 'account', 'services', 'faq'):
            with self.subTest(page=page):
                response = self.client.get('/api/pages/' + page, headers=headers)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers['Cache-Control'], 'no-store')
                html = response.json['html']
                self.assertNotIn(self.db.token(self.alice['id']), html)
                self.assertLess(html.index('/static/js/api.js'), html.index('/static/js/site.js'))
                parser = Assets()
                parser.feed(html)
                for asset in parser.urls:
                    with self.client.get(asset) as asset_response:
                        self.assertEqual(asset_response.status_code, 200, asset)

    def test_admin_navigation_targets_completed_admin_pages(self):
        headers = self.login(self.admin)
        expected = {'member': '/admin', 'history': '/admin/history'}
        for page, target in expected.items():
            with self.subTest(page=page):
                response = self.client.get('/api/pages/' + page, headers=headers)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json, {'ok': True, 'redirect': target})
        for page in ('admin', 'history-admin', 'tasks', 'announcement', 'member_donate'):
            with self.subTest(page=page):
                response = self.client.get('/api/pages/' + page, headers=headers)
                self.assertEqual(response.status_code, 200)
                self.assertNotIn('redirect', response.json)

    def test_admin_dashboard_loads_for_admin_with_all_local_assets(self):
        headers = self.login(self.admin)
        response = self.client.get('/api/pages/admin', headers=headers)
        self.assertEqual(response.status_code, 200)
        html = response.json['html']
        self.assertIn('Admin Dashboard', html)
        self.assertNotIn(self.db.token(self.admin['id']), html)
        parser = Assets()
        parser.feed(html)
        for asset in parser.urls:
            with self.client.get(asset) as asset_response:
                self.assertEqual(asset_response.status_code, 200, asset)

    def test_tasks_page_loads_its_case_sensitive_asset_and_exposes_pickup_only_to_volunteers(self):
        for actor, can_pick in ((self.alice, 'true'), (self.admin, 'false')):
            with self.subTest(role=actor['role']):
                html, _ = self.rendered('tasks', self.login(actor))
                self.assertIn(f'data-can-pick="{can_pick}"', html)
                parser = Assets()
                parser.feed(html)
                script = next(url for url in parser.urls if url.lower() == '/static/js/task.js')
                # A macOS test client can serve the wrong case from disk; Render cannot.
                self.assertIn(script.rsplit('/', 1)[-1],
                              {path.name for path in (main.SITE_DIR / 'static/js').iterdir()})

    def test_volunteer_cannot_load_admin_templates_or_spoof_role(self):
        headers = self.login()
        for page in ('admin', 'history-admin'):
            response = self.client.get('/api/pages/' + page, headers=headers,
                                       query_string={'role': 'admin', 'user_id': self.admin['id']})
            self.assertEqual(response.status_code, 403)
            self.assertNotIn('html', response.json)

    def test_current_profile_role_controls_access(self):
        headers = self.login(self.admin)
        self.db.row('profiles', self.admin['id'])['role'] = 'volunteer'
        self.assertEqual(self.client.get('/api/pages/history-admin', headers=headers).status_code, 403)
        self.db.row('profiles', self.admin['id'])['role'] = 'unsupported'
        self.assertEqual(self.client.get('/api/pages/member', headers=headers).status_code, 403)

    def test_bearer_token_is_revalidated_on_each_page_request(self):
        headers = self.login(self.admin)
        self.assertEqual(self.client.get('/api/pages/history-admin', headers=headers).status_code, 200)
        self.db.expired_tokens.add(self.db.token(self.admin['id']))
        response = self.client.get('/api/pages/history-admin', headers=headers)
        self.assertEqual(response.status_code, 401)
        self.assertNotIn('html', response.json)

    def test_all_page_api_responses_disable_public_caching(self):
        for actor in (self.alice, self.admin):
            headers = self.login(actor)
            for page in PAGE_URLS:
                with self.subTest(actor=actor['role'], page=page):
                    response = self.client.get('/api/pages/' + page, headers=headers)
                    self.assertIn(response.status_code, (200, 403))
                    self.assertTrue(response.cache_control.no_store)
                    self.assertFalse(response.cache_control.public)
                    self.assertNotIn('Set-Cookie', response.headers)

    def test_invalid_and_expired_tokens_cannot_render_history(self):
        for token in ('invalid', self.db.token(self.alice['id'])):
            with self.subTest(token=token):
                self.db.expired_tokens.add(token)
                with patch.object(main.History, 'service_history') as service_history:
                    response = self.client.get('/api/pages/history', headers={'Authorization': 'Bearer ' + token})
                    self.assertEqual(response.status_code, 401)
                    self.assertNotIn('html', response.json)
                    service_history.assert_not_called()

    def test_volunteer_history_contains_only_own_completed_work(self):
        self.add_bob_completion()
        self.db.tables['assignments'][1]['reviewed_at'] = '2026-10-21T12:00:00+00:00'
        for status in ('assigned', 'submitted', 'cancelled'):
            self.db.tables['assignments'].append(self.db.defaults('assignments', {
                'task_id': self.db.fixture['tasks'][1]['id'], 'volunteer_id': self.alice['id'], 'status': status,
            }))
        html, context = self.rendered('history', self.login(), '?volunteer_id=' + self.bob['id'])
        self.assertEqual(context['total_hours'], 1.5)
        self.assertEqual(context['member_tasks'], [{
            'date': '2026-10-21', 'title': '[MOCK CIC] Prior delivery', 'status': 'completed',
            'hours': 1.5, 'member_id': self.alice['id'],
        }])
        self.assertNotIn('[MOCK CIC] Event setup', html)
        self.assertIn('Total estimated hours', html)
        self.assertIn('Actual time is not recorded', html)

    def test_admin_history_includes_both_volunteers_with_distinct_ids(self):
        self.add_bob_completion()
        self.db.row('profiles', self.bob['id']).update(first_name='Alice', last_name='Volunteer')
        html, context = self.rendered('history-admin', self.login(self.admin))
        rows = context['all_tasks']
        self.assertEqual(len(rows), 2)
        self.assertEqual(sum(row['hours'] for row in rows), 4.5)
        self.assertEqual({row['member_id'] for row in rows}, {self.alice['id'], self.bob['id']})
        self.assertTrue(all(row['member'] == 'Alice Volunteer' for row in rows))
        self.assertIn('Total estimated volunteer hours', html)
        for user_id in (self.alice['id'], self.bob['id']):
            self.assertIn(f'<option value="{user_id}">Alice Volunteer</option>', html)

    def test_empty_histories_have_no_invented_rows(self):
        html, context = self.rendered('history', self.login(self.bob))
        self.assertEqual(context['member_tasks'], [])
        self.assertEqual(context['total_hours'], 0)
        self.assertIn("You haven't completed any tasks yet", html)
        self.db.tables['assignments'] = []
        html, context = self.rendered('history-admin', self.login(self.admin))
        self.assertEqual(context['all_tasks'], [])
        self.assertIn('No tasks have been completed yet', html)

    def test_query_failure_does_not_masquerade_as_empty_history(self):
        headers = self.login()
        with patch.object(main.History, 'service_history', return_value=None), self.assertLogs(main.app.logger, level='ERROR'):
            response = self.client.get('/api/pages/history', headers=headers)
        self.assertEqual(response.status_code, 500)
        self.assertNotIn('html', response.json)
        self.assertEqual(response.json['error'], 'Could not load page')

    def test_missing_profile_fails_closed(self):
        headers = self.login()
        self.db.tables['profiles'] = [row for row in self.db.tables['profiles'] if row['id'] != self.alice['id']]
        with self.assertLogs(main.app.logger, level='ERROR'), patch.object(main.History, 'service_history') as service_history:
            response = self.client.get('/api/pages/history', headers=headers)
        self.assertEqual(response.status_code, 500)
        self.assertNotIn('html', response.json)
        service_history.assert_not_called()

    def test_database_names_and_task_titles_remain_escaped(self):
        self.db.row('profiles', self.alice['id'])['first_name'] = '<script>alert("name")</script>'
        self.db.row('tasks', self.db.fixture['tasks'][3]['id'])['title'] = '<script>alert("task")</script>'
        html, _ = self.rendered('history-admin', self.login(self.admin))
        self.assertIn('&lt;script&gt;', html)
        self.assertNotIn('<script>alert("name")</script>', html)
        self.assertNotIn('<script>alert("task")</script>', html)

    def test_history_reads_use_the_verified_bearer_token_for_rls(self):
        for actor, page in ((self.alice, 'history'), (self.admin, 'history-admin')):
            with self.subTest(page=page):
                headers = self.login(actor)
                clients = []

                def client_factory(*args, **kwargs):
                    client = self.db.client()
                    clients.append(client)
                    return client

                with patch.object(history, 'create_client', side_effect=client_factory):
                    self.assertEqual(self.client.get('/api/pages/' + page, headers=headers).status_code, 200)
                self.assertEqual(len(clients), 1)
                self.assertEqual(clients[0].user_id, actor['id'])
                self.assertEqual(clients[0].options.headers['Authorization'], headers['Authorization'])

    def test_unfinished_entries_explain_status_and_return_to_the_correct_dashboard(self):
        for actor, endpoint in ((self.alice, 'member_dashboard'), (self.admin, 'admin_dashboard')):
            headers = self.login(actor)
            for page in ('account', 'services', 'faq'):
                with self.subTest(role=actor['role'], page=page):
                    html, context = self.rendered(page, headers)
                    self.assertIn('not available', html)
                    self.assertIn('Back to dashboard', html)
                    self.assertEqual(context['dashboard_endpoint'], endpoint)

    def test_unknown_page_names_stay_unavailable(self):
        headers = self.login()
        for path in ('/missing', '/base.html'):
            self.assertEqual(self.client.get(path).status_code, 404, path)
        for page in ('task', 'base', 'missing'):
            response = self.client.get('/api/pages/' + page, headers=headers)
            self.assertEqual(response.status_code, 404, page)
            self.assertNotIn('html', response.json)


if __name__ == '__main__':
    unittest.main()
