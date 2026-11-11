// Checks the frontend against contract/openapi.json, the API snapshot the backend
// tests keep up to date. A failure here means the frontend and backend disagree.
import { describe, expect, it } from 'vitest'
import contract from '../../../contract/openapi.json'
import analysisView from '../views/AnalysisView.vue?raw'
import authForm from '../components/AuthForm.vue?raw'
import useAuth from '../composables/useAuth.js?raw'
import profileView from '../views/ProfileView.vue?raw'
import tabletDemoView from '../views/TabletDemoView.vue?raw'
import connectionTest from '../components/ConnectionTest.vue?raw'
import tabletReadingView from '../views/TabletReadingView.vue?raw'
import glyphPane from '../components/glyphs/GlyphOccurrencesPane.vue?raw'

// Every call the frontend makes: the snippet must still be in the source file,
// and the endpoint must exist in the contract.
const CALLS = [
  { method: 'post', path: '/users/register', source: authForm, snippet: '/api/users/${props.mode}' },
  { method: 'post', path: '/users/login', source: authForm, snippet: '/api/users/${props.mode}' },
  { method: 'post', path: '/users/register', source: useAuth, snippet: '/api/users/${mode}' },
  { method: 'post', path: '/users/login', source: useAuth, snippet: '/api/users/${mode}' },
  { method: 'get', path: '/users/{user_id}/username', source: profileView, snippet: '/api/users/${userId.value}/username' },
  { method: 'get', path: '/users/{user_id}/email', source: profileView, snippet: '/api/users/${userId.value}/email' },
  { method: 'get', path: '/tablet-demo/ht13', source: tabletDemoView, snippet: '/api/tablet-demo/ht13?annotated=false' },
  { method: 'get', path: '/tablet-demo/ht13/predictions', source: tabletDemoView, snippet: '/api/tablet-demo/ht13/predictions' },
  { method: 'post', path: '/analysis', source: analysisView, snippet: "'/api/analysis'" },
  { method: 'get', path: '/health', source: connectionTest, snippet: "'/api/health'" },
  { method: 'get', path: '/tablets/{slug}/reading', source: tabletReadingView, snippet: '/api/tablets/${slug}/reading' },
  { method: 'get', path: '/tablets/{slug}/fraction-signs', source: tabletReadingView, snippet: '/api/tablets/${slug}/fraction-signs' },
  { method: 'get', path: '/tablet-demo/ht13', source: tabletReadingView, snippet: '/api/tablet-demo/ht13?annotated=false' },
  { method: 'get', path: '/glyphs/{sign}/occurrences', source: glyphPane, snippet: '/api/glyphs/${sign}/occurrences?${query}' },
  { method: 'post', path: '/glyphs/{sign}/occurrences/search', source: glyphPane, snippet: '/api/glyphs/${sign}/occurrences/search' },
  { method: 'get', path: '/glyphs/{sign}/annotations', source: glyphPane, snippet: '/api/glyphs/${sign}/annotations' },
  { method: 'post', path: '/glyphs/{sign}/annotations', source: glyphPane, snippet: '/api/glyphs/${active.value}/annotations' },
  { method: 'delete', path: '/glyphs/annotations/{annotation_id}', source: glyphPane, snippet: '/api/glyphs/annotations/${comment.id}' },
  { method: 'get', path: '/tablets/{slug}/thumbnail.png', source: glyphPane, snippet: 'apiUrl(item.thumbnail_url)' },
  { method: 'get', path: '/tablets/{slug}/signs/{position}.png', source: glyphPane, snippet: 'apiUrl(item.crop_url)' },
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
  it.each(CALLS)('$method $path is called by the frontend and exists in the API', ({ method, path, source, snippet }) => {
    expect(source).toContain(snippet)
    expect(contract.paths[path]?.[method]).toBeDefined()
  })

  it('register and login accept the fields the frontend sends', () => {
    expect(requestFields('post', '/users/register')).toEqual(expect.arrayContaining(['email', 'username', 'password']))
    expect(requestFields('post', '/users/login')).toEqual(expect.arrayContaining(['email', 'username', 'password']))
  })

  it('login returns the authenticated flag and user id and email the frontend reads', () => {
    expect(responseFields('post', '/users/login', '200')).toEqual(expect.arrayContaining(['authenticated', 'user']))
    const user = resolve(resolve(contract.components.schemas.LoginResponse).properties.user)
    expect(Object.keys(user.properties)).toEqual(expect.arrayContaining(['id', 'email', 'username']))
  })

  it('profile endpoints return the username and email ProfileView reads', () => {
    expect(responseFields('get', '/users/{user_id}/username', '200')).toContain('username')
    expect(responseFields('get', '/users/{user_id}/email', '200')).toContain('email')
  })

  // Guards against #30 coming back: the page rendered a field the API never returned.
  it('AnalysisView renders only fields of AnalysisResult', () => {
    expect(ANALYSIS_FIELDS).toEqual(expect.arrayContaining(['summary', 'signs', 'formulas']))
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
