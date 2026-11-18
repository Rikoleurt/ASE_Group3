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
import benchmarksView from '../views/BenchmarksView.vue?raw'
import glyphPane from '../components/glyphs/GlyphOccurrencesPane.vue?raw'
import signCorrection from '../components/analysis/SignCorrection.vue?raw'
import reviewView from '../views/ReviewView.vue?raw'
import adminView from '../views/AdminView.vue?raw'
import useBoxSet from '../composables/useBoxSet.js?raw'
import tabletsView from '../views/TabletsView.vue?raw'
import shareDialog from '../components/boxes/ShareDialog.vue?raw'
import sharedView from '../views/SharedView.vue?raw'
import historyPanel from '../components/boxes/HistoryPanel.vue?raw'
import boxComments from '../components/boxes/BoxComments.vue?raw'

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
  // The session (#65): the profile reads the logged-in user from /users/me, not by id.
  { method: 'get', path: '/users/me', source: session, snippet: "'/api/users/me'" },
  { method: 'post', path: '/users/logout', source: session, snippet: "'/api/users/logout'" },
  { method: 'get', path: '/users/me/analyses', source: historyView, snippet: '/api/users/me/analyses?limit=20' },
  { method: 'get', path: '/users/me/analyses/{analysis_id}', source: historyDetailView, snippet: '/api/users/me/analyses/${encodeURIComponent(route.params.id)}' },
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
  { method: 'get', path: '/benchmarks', source: benchmarksView, snippet: "'/api/benchmarks'" },
  { method: 'get', path: '/benchmarks/{version}', source: benchmarksView, snippet: '/api/benchmarks/${encodeURIComponent(name)}' },
  { method: 'get', path: '/glyphs/{sign}/occurrences', source: glyphPane, snippet: '/api/glyphs/${sign}/occurrences?${query}' },
  { method: 'post', path: '/glyphs/{sign}/occurrences/search', source: glyphPane, snippet: '/api/glyphs/${sign}/occurrences/search' },
  { method: 'get', path: '/glyphs/characters', source: glyphPane, snippet: '/api/glyphs/characters?signs=' },
  { method: 'get', path: '/glyphs/characters', source: tabletDemoView, snippet: '/api/glyphs/characters?signs=' },
  { method: 'get', path: '/glyphs/{sign}/annotations', source: glyphPane, snippet: '/api/glyphs/${sign}/annotations' },
  { method: 'post', path: '/glyphs/{sign}/annotations', source: glyphPane, snippet: '/api/glyphs/${sign}/annotations' },
  { method: 'delete', path: '/glyphs/annotations/{annotation_id}', source: glyphPane, snippet: '/api/glyphs/annotations/${comment.id}' },
  { method: 'get', path: '/tablets/{slug}/thumbnail.png', source: glyphPane, snippet: 'apiUrl(item.thumbnail_url)' },
  { method: 'get', path: '/tablets/{slug}/signs/{position}.png', source: glyphPane, snippet: 'apiUrl(item.crop_url)' },
  { method: 'get', path: '/corrections/catalogue', source: analysisView, snippet: "'/api/corrections/catalogue'" },
  { method: 'post', path: '/analysis/{analysis_id}/corrections', source: signCorrection, snippet: '/api/analysis/${props.analysisId}/corrections' },
  { method: 'get', path: '/corrections', source: reviewView, snippet: '/api/corrections?status=${STATUS.value}&limit=200' },
  { method: 'post', path: '/corrections/{correction_id}/review', source: reviewView, snippet: '/api/corrections/${item.id}/review' },
  { method: 'get', path: '/corrections/export', source: reviewView, snippet: "'/api/corrections/export'" },
  { method: 'get', path: '/corrections/catalogue', source: reviewView, snippet: "'/api/corrections/catalogue'" },
  { method: 'get', path: '/admin/users', source: adminView, snippet: '/api/admin/users?${query}' },
  { method: 'get', path: '/admin/export/corrections', source: adminView, snippet: "'/api/admin/export/corrections'" },
  { method: 'get', path: '/admin/export/corrections.zip', source: adminView, snippet: "'/api/admin/export/corrections.zip'" },
  { method: 'post', path: '/box-sets', source: useBoxSet, snippet: "'/api/box-sets'" },
  { method: 'get', path: '/box-sets/{set_id}', source: useBoxSet, snippet: '/api/box-sets/${encodeURIComponent(id)}' },
  { method: 'patch', path: '/box-sets/{set_id}', source: useBoxSet, snippet: '/api/box-sets/${copy.value.id}' },
  { method: 'get', path: '/tablets', source: tabletsView, snippet: '/api/tablets?${query}' },
  { method: 'get', path: '/box-sets/{set_id}/shares', source: shareDialog, snippet: '/api/box-sets/${props.setId}/shares' },
  { method: 'put', path: '/box-sets/{set_id}/shares/{user_id}', source: shareDialog, snippet: '/api/box-sets/${props.setId}/shares/${user.id}' },
  { method: 'delete', path: '/box-sets/{set_id}/shares/{user_id}', source: shareDialog, snippet: '/api/box-sets/${props.setId}/shares/${user.id}' },
  { method: 'put', path: '/box-sets/{set_id}/everyone', source: shareDialog, snippet: '/api/box-sets/${props.setId}/everyone' },
  { method: 'get', path: '/users/search', source: shareDialog, snippet: '/api/users/search?q=${encodeURIComponent(query)}' },
  { method: 'get', path: '/users/me/shared-copies', source: sharedView, snippet: "'/api/users/me/shared-copies'" },
  { method: 'get', path: '/box-sets/{set_id}/changes', source: historyPanel, snippet: '/api/box-sets/${props.setId}/changes?${query}' },
  { method: 'post', path: '/box-sets/{set_id}/changes/{change_id}/revert', source: historyPanel, snippet: '/api/box-sets/${props.setId}/changes/${change.id}/revert' },
  { method: 'get', path: '/box-sets/{set_id}/comments', source: boxComments, snippet: '/api/box-sets/${props.setId}/comments' },
  { method: 'post', path: '/box-sets/{set_id}/comments', source: boxComments, snippet: '/api/box-sets/${props.setId}/comments' },
  { method: 'delete', path: '/box-sets/{set_id}/comments/{comment_id}', source: boxComments, snippet: '/api/box-sets/${props.setId}/comments/${comment.id}' },
  { method: 'get', path: '/tablets/{slug}/boxes', source: tabletsView, snippet: '/api/tablets/${encodeURIComponent(SLUG.value)}/boxes?source=${SOURCE.value}' },
  { method: 'get', path: '/tablets/{slug}/box-set', source: tabletsView, snippet: '/api/tablets/${encodeURIComponent(slug)}/box-set' },
  { method: 'post', path: '/box-sets', source: tabletsView, snippet: "'/api/box-sets'" },
  { method: 'patch', path: '/admin/users/{user_id}', source: adminView, snippet: '/api/admin/users/${user.id}' },
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
    expect(contract.paths['/community/discussions'].post.security).toEqual([{APIKeyCookie: []}])
    expect(requestFields('post', '/community/discussions')).toEqual(expect.arrayContaining(['analysis_id', 'title']))
    expect(requestFields('post', '/community/discussions/{discussion_id}/comments')).toEqual(['body'])
  })
  it.each(CALLS)('$method $path is called by the frontend and exists in the API', ({
                                                                                     method,
                                                                                     path,
                                                                                     source,
                                                                                     snippet
                                                                                   }) => {
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

  it('the session returns the user and the CSRF token the frontend reads', () => {
    expect(responseFields('get', '/users/me', '200')).toEqual(expect.arrayContaining(['user', 'csrf_token']))
    expect(session).toContain('csrf_token')
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

  it('corrections accept what the correction form sends and return what it shows', () => {
    expect(requestFields('post', '/analysis/{analysis_id}/corrections')).toEqual(
      expect.arrayContaining(['sign_id', 'proposed_sign', 'uncertain', 'note']),
    )
    expect(responseFields('post', '/analysis/{analysis_id}/corrections', '201')).toContain('uncertain')
    expect(responseFields('post', '/analysis', '200')).toContain('analysis_id')
    expect(requestFields('post', '/corrections/{correction_id}/review')).toEqual(['decision'])
  })

  it('the session says whether the user reviews corrections and administers roles', () => {
    for (const role of ['reviewer', 'admin']) {
      expect(responseFields('get', '/users/me', '200')).toContain(role)
      expect(responseFields('post', '/users/login', '200')).toContain(role)
    }
  })

  it('the box editor sends the change shapes the API declares and reads the copy it returns', () => {
    expect(requestFields('patch', '/box-sets/{set_id}').sort()).toEqual(['changes', 'version'])
    for (const field of ['op', 'box', 'sign', 'box_id']) expect(useBoxSet).toContain(field)
    expect(responseFields('patch', '/box-sets/{set_id}', '200')).toEqual(
      expect.arrayContaining(['id', 'version', 'boxes', 'reading', 'image_url', 'source']),
    )
    expect(responseFields('patch', '/box-sets/{set_id}', '409').sort()).toEqual(['current', 'detail'])
    expect(requestFields('post', '/box-sets').sort()).toEqual(['analysis_id', 'start', 'tablet'])
  })

  it('sharing sends and reads the declared fields', () => {
    expect(requestFields('put', '/box-sets/{set_id}/shares/{user_id}')).toEqual(['permission'])
    expect(requestFields('put', '/box-sets/{set_id}/everyone')).toEqual(['permission'])
    expect(responseFields('get', '/box-sets/{set_id}/shares', '200').sort()).toEqual(['everyone', 'shares'])
    expect(responseFields('get', '/box-sets/{set_id}', '200')).toEqual(expect.arrayContaining(['permission', 'everyone', 'owner']))
  })

  it('history and comments read the declared fields', () => {
    expect(responseFields('get', '/box-sets/{set_id}/changes', '200').sort()).toEqual(['items', 'next_before'])
    expect(requestFields('post', '/box-sets/{set_id}/comments').sort()).toEqual(['body', 'box_id'])
    expect(responseFields('post', '/box-sets/{set_id}/comments', '201')).toEqual(
      expect.arrayContaining(['id', 'box_id', 'author', 'body', 'created_at', 'can_delete']),
    )
  })

  it('the admin page sends and reads only declared role fields', () => {
    expect(requestFields('patch', '/admin/users/{user_id}')).toEqual(['admin', 'reviewer'])
    expect(responseFields('patch', '/admin/users/{user_id}', '200')).toEqual(
      expect.arrayContaining(['id', 'username', 'email', 'admin', 'reviewer', 'reviewer_from_env']),
    )
    expect(responseFields('get', '/admin/users', '200')).toEqual(expect.arrayContaining(['items', 'total']))
  })

  // Guards against #30 coming back: the page rendered a field the API never returned.
  it('AnalysisView renders only fields of SavedAnalysisResult', () => {
    expect(ANALYSIS_FIELDS).toEqual(expect.arrayContaining(['summary', 'signs', 'formulas', 'analysis_id']))
    const returned = responseFields('post', '/analysis', '200')
    expect(ANALYSIS_FIELDS.filter((field) => !returned.includes(field))).toEqual([])
  })

  // The pane only reads fields the API declares.
  it.each([
    ['item', 'GlyphOccurrence'],
    ['comment', 'Annotation'],
    ['page', 'GlyphOccurrencePage', 'AnnotationPage'],
  ])('GlyphOccurrencesPane reads only fields of %s', (root, ...schemas) => {
    const declared = schemas.flatMap((schema) => Object.keys(contract.components.schemas[schema].properties))
    const used = [...glyphPane.matchAll(new RegExp(root + '\\.(\\w+)', 'g'))].map((m) => m[1])
    expect(used.length).toBeGreaterThan(0)
    expect(used.filter((field) => !declared.includes(field))).toEqual([])
  })
})
