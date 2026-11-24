// Checks the frontend against contract/openapi.json, the API snapshot the backend
// tests keep up to date. A failure here means the frontend and backend disagree.
import { describe, expect, it } from 'vitest'
import contract from '../../../contract/openapi.json'
import analysisView from '../views/AnalysisView.vue?raw'
import authForm from '../components/AuthForm.vue?raw'
import useAuth from '../composables/useAuth.js?raw'
import session from '../state/session.js?raw'
import historyView from '../views/HistoryView.vue?raw'
import historyDetailView from '../views/HistoryDetailView.vue?raw'
import tabletDemoView from '../views/TabletDemoView.vue?raw'
import connectionTest from '../components/ConnectionTest.vue?raw'
import tabletReadingView from '../views/TabletReadingView.vue?raw'
import shareAnalysis from '../components/ShareAnalysis.vue?raw'
import communityView from '../views/CommunityView.vue?raw'
import discussionView from '../views/DiscussionView.vue?raw'

// Every call the frontend makes: the snippet must still be in the source file,
// and the endpoint must exist in the contract.
const CALLS = [
  { method: 'post', path: '/community/discussions', source: shareAnalysis, snippet: "communityApi('/discussions'" },
  { method: 'get', path: '/community/discussions', source: communityView, snippet: '/discussions?limit=20' },
  { method: 'get', path: '/community/discussions/{discussion_id}', source: discussionView, snippet: 'communityApi(`/discussions/${id}`)' },
  { method: 'get', path: '/community/discussions/{discussion_id}/comments', source: discussionView, snippet: 'communityApi(`/discussions/${id}/comments`)' },
  { method: 'post', path: '/community/discussions/{discussion_id}/comments', source: discussionView, snippet: 'communityApi(`/discussions/${id}/comments`, {' },
  { method: 'post', path: '/users/register', source: authForm, snippet: '/api/users/${props.mode}' },
  { method: 'post', path: '/users/login', source: authForm, snippet: '/api/users/${props.mode}' },
  { method: 'post', path: '/users/register', source: useAuth, snippet: '/api/users/${mode}' },
  { method: 'post', path: '/users/login', source: useAuth, snippet: '/api/users/${mode}' },
  { method: 'get', path: '/users/me', source: session, snippet: "'/api/users/me'" },
  { method: 'post', path: '/users/logout', source: session, snippet: "'/api/users/logout'" },
  { method: 'get', path: '/users/me/analyses', source: historyView, snippet: '/api/users/me/analyses?limit=20${query}' },
  { method: 'get', path: '/users/me/analyses/{analysis_id}', source: historyDetailView, snippet: '/api/users/me/analyses/${encodeURIComponent(route.params.id)}' },
  { method: 'get', path: '/tablet-demo/ht13', source: tabletDemoView, snippet: '/api/tablet-demo/ht13?annotated=false' },
  { method: 'get', path: '/tablet-demo/ht13/predictions', source: tabletDemoView, snippet: '/api/tablet-demo/ht13/predictions' },
  { method: 'post', path: '/analysis', source: analysisView, snippet: "'/api/analysis'" },
  { method: 'get', path: '/health', source: connectionTest, snippet: "'/api/health'" },
  { method: 'get', path: '/tablets/{slug}/reading', source: tabletReadingView, snippet: '/api/tablets/${slug}/reading' },
  { method: 'get', path: '/tablets/{slug}/fraction-signs', source: tabletReadingView, snippet: '/api/tablets/${slug}/fraction-signs' },
  { method: 'get', path: '/tablet-demo/ht13', source: tabletReadingView, snippet: '/api/tablet-demo/ht13?annotated=false' },
]

function resolve(schema) {
  const ref = schema?.$ref
  return ref ? contract.components.schemas[ref.split('/').pop()] : schema
}

function responseFields(method, path, status) {
  const schema = contract.paths[path][method].responses[status].content['application/json'].schema
  return Object.keys(resolve(schema).properties ?? {})
}

function requestFields(method, path) {
  const body = contract.paths[path][method].requestBody.content
  const schema = Object.values(body)[0].schema
  return Object.keys(resolve(schema).properties ?? {})
}

// Fields AnalysisView renders, read from its template: `ANALYSIS.<field>`. Only the
// template is scanned, because the script's `ANALYSIS.value` is the ref itself.
const ANALYSIS_TEMPLATE = analysisView.slice(analysisView.indexOf('<template>'))
const ANALYSIS_FIELDS = [...new Set([...ANALYSIS_TEMPLATE.matchAll(/ANALYSIS\.(\w+)/g)].map((m) => m[1]))]

describe('API contract', () => {
  it('provides the community author, image and analysis without requiring a session to read', () => {
    expect(responseFields('get', '/community/discussions/{discussion_id}', '200')).toEqual(
      expect.arrayContaining(['id', 'title', 'author_username', 'created_at', 'image_url', 'result']),
    )
    const operation = contract.paths['/community/discussions/{discussion_id}'].get
    expect(operation.security).toBeUndefined()
    expect(contract.paths['/community/discussions'].post.security).toEqual([{ APIKeyCookie: [] }])
    expect(requestFields('post', '/community/discussions')).toEqual(expect.arrayContaining(['analysis_id', 'title']))
    expect(requestFields('post', '/community/discussions/{discussion_id}/comments')).toEqual(['body'])
  })
  it.each(CALLS)('$method $path is called by the frontend and exists in the API', ({ method, path, source, snippet }) => {
    expect(source).toContain(snippet)
    expect(contract.paths[path]?.[method]).toBeDefined()
  })

  it('register and login accept the fields the frontend sends', () => {
    expect(requestFields('post', '/users/register')).toEqual(expect.arrayContaining(['email', 'username', 'password']))
    expect(requestFields('post', '/users/login')).toEqual(expect.arrayContaining(['email', 'username', 'password']))
  })

  it('login returns the authenticated flag and user id and email the frontend reads', () => {
    expect(responseFields('post', '/users/login', '200')).toEqual(expect.arrayContaining(['authenticated', 'user', 'csrf_token']))
    const user = resolve(resolve(contract.components.schemas.LoginResponse).properties.user)
    expect(Object.keys(user.properties)).toEqual(expect.arrayContaining(['id', 'email', 'username']))
  })

  it('the session returns the user and CSRF token used by the frontend', () => {
    expect(responseFields('get', '/users/me', '200')).toEqual(expect.arrayContaining(['user', 'csrf_token']))
    const user = resolve(contract.components.schemas.SessionUser.properties.user)
    expect(Object.keys(user.properties)).toEqual(expect.arrayContaining(['id', 'username', 'email']))
  })

  it('history returns pagination, metadata and the saved analysis', () => {
    expect(responseFields('get', '/users/me/analyses', '200')).toEqual(expect.arrayContaining(['items', 'next_cursor']))
    const metadata = resolve(contract.components.schemas.AnalysisHistoryPage.properties.items.items)
    expect(Object.keys(metadata.properties)).toEqual(expect.arrayContaining(['id', 'filename', 'created_at']))
    expect(responseFields('get', '/users/me/analyses/{analysis_id}', '200')).toEqual(
      expect.arrayContaining(['filename', 'created_at', 'format', 'size_bytes', 'result']),
    )
    const result = resolve(contract.components.schemas.AnalysisHistoryDetail.properties.result)
    expect(Object.keys(result.properties)).toEqual(
      expect.arrayContaining(['summary', 'symbol_interpretation', 'confidence', 'time_taken', 'signs', 'formulas']),
    )
  })

  // Guards against #30 coming back: the page rendered a field the API never returned.
  it('AnalysisView renders only fields of SavedAnalysisResult', () => {
    expect(ANALYSIS_FIELDS).toEqual(expect.arrayContaining(['summary', 'signs', 'formulas', 'analysis_id']))
    const returned = responseFields('post', '/analysis', '200')
    expect(ANALYSIS_FIELDS.filter((field) => !returned.includes(field))).toEqual([])
  })
})
