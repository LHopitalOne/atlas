import unittest

from .support import Repository

SOURCE = """
import { getConfig } from '@edx/frontend-platform';
import { getAuthenticatedHttpClient } from '@edx/frontend-platform/auth';

export const getBookmarksBaseUrl = () => `${getConfig().LMS_BASE_URL}/api/bookmarks/v1/bookmarks/`;
const handlerUrl = (courseId, blockId) => `${getConfig().LMS_BASE_URL}/courses/${courseId}/xblock/${blockId}/handler`;

function goalsUrl() {
  const base = getConfig().LMS_BASE_URL;
  return `${base}/api/course_home/save_course_goal`;
}

function notAUrl() {
  return 42;
}

export async function createBookmark(usageId) {
  return getAuthenticatedHttpClient().post(getBookmarksBaseUrl(), { usage_id: usageId });
}

export async function deleteBookmark(username, usageId) {
  return getAuthenticatedHttpClient().delete(`${getBookmarksBaseUrl()}${username},${usageId}/`);
}

export async function getCompletion(courseId, blockId) {
  return getAuthenticatedHttpClient().post(`${handlerUrl(courseId, blockId)}/get_completion`, {});
}

export async function saveGoal() {
  return getAuthenticatedHttpClient().post(goalsUrl(), {});
}

export async function dismiss(courseId) {
  const url = new URL(`${getConfig().LMS_BASE_URL}/api/course_home/dismiss_welcome_message`);
  return getAuthenticatedHttpClient().post(url.href, { course_id: courseId });
}

export async function deadlines() {
  const url = new URL(`${getConfig().LMS_BASE_URL}/api/course_experience/v1/reset_course_deadlines`);
  return getAuthenticatedHttpClient().post(url.toString(), {});
}

export async function unknown() {
  return getAuthenticatedHttpClient().get(notAUrl());
}
"""


class UrlHelpersTest(unittest.TestCase):
    def test_helpers_and_url_objects(self):
        calls = Repository.calls(SOURCE, 'src/data/api.js')
        self.assertTrue(
            {
                ('POST', '/api/bookmarks/v1/bookmarks'),
                ('DELETE', '/api/bookmarks/v1/bookmarks/{username},{usageId}'),
                ('POST', '/courses/{courseId}/xblock/{blockId}/handler/get_completion'),
                ('POST', '/api/course_home/save_course_goal'),
                ('POST', '/api/course_home/dismiss_welcome_message'),
                ('POST', '/api/course_experience/v1/reset_course_deadlines'),
            }
            <= set(calls)
        )
        bookmark = calls['POST', '/api/bookmarks/v1/bookmarks']
        self.assertIn('getBookmarksBaseUrl', bookmark.hints)
        self.assertIn('getConfig().LMS_BASE_URL', bookmark.hints)
        self.assertFalse(any(path == '/42' for _, path in calls))


if __name__ == '__main__':
    unittest.main()
