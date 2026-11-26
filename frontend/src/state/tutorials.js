// The onboarding lessons on the Tutorials page: short walkthroughs recorded from the real app
// (frontend/public/tutorials/<id>.mp4, poster <id>.jpg). In the order a new scholar meets them.
import { ref, watch } from 'vue'

export const SECTIONS = [
  {
    title: 'Get started',
    lessons: [
      {
        id: 'getting-around',
        title: 'Find your way around',
        summary:
          'A quick tour of the main pages and where to find your notifications and settings.',
        steps: [
          'Analysis reads a tablet image you upload.',
          'Tablets lists every published tablet in the corpus.',
          'Signs looks up any sign, even from a sketch.',
          'Community is where readings are discussed.',
          'Tutorials, like this one, are always one click away.',
          'The bell and your account menu are on the right.',
        ],
        tryIt: { to: '/', label: 'Go to the home page' },
      },
      {
        id: 'read-a-tablet',
        title: 'Read a tablet',
        summary: 'Upload a photo or drawing and let the reader find and name its signs.',
        steps: [
          'Open Analysis and upload a PNG or JPEG of a tablet.',
          'Each sign the reader finds gets a box, coloured by kind of sign.',
          'Point at a box to see its reading and how sure the reader is.',
          'Below, read the transliteration and the fraction check.',
        ],
        tryIt: { to: '/analysis', label: 'Open Analysis' },
      },
      {
        id: 'browse-the-corpus',
        title: 'Browse the corpus',
        summary: 'Open any published tablet and compare the scholars’ boxes with the reader’s.',
        steps: [
          'Search the Tablets page by tablet name, such as HT 13.',
          'The tracing shows the scholars’ published sign boxes.',
          'Switch to the model’s boxes to see the reader’s version.',
          'Star a tablet to keep it at the top of your list.',
        ],
        tryIt: { to: '/tablets/HT-13', label: 'Open HT 13' },
      },
      {
        id: 'find-a-sign',
        title: 'Find a sign',
        summary:
          'Look up a sign by number, reading or name, or draw it if you only know its shape.',
        steps: [
          'Type a number (AB81), a reading (ku) or a name.',
          'Or draw the sign in the box: the closest matches appear as you draw.',
          'Open a sign to see where it occurs across the corpus.',
        ],
        tryIt: { to: '/signs', label: 'Find a sign' },
      },
    ],
  },
  {
    title: 'Correct readings',
    lessons: [
      {
        id: 'correct-the-boxes',
        title: 'Correct the boxes',
        summary: 'Fix boxes and signs in your own copy. The original is never changed.',
        steps: [
          'Choose Correct the boxes on a tablet to start your own copy.',
          'Click a box to select it; drag it to move, or a corner to resize.',
          'Draw a box adds a new one; name it from the sign list.',
          'Nothing is kept until you press Save, and every save goes into the history.',
        ],
        tryIt: { to: '/tablets/HT-13', label: 'Correct HT 13' },
      },
      {
        id: 'mark-damage',
        title: 'Mark uncertain and damaged signs',
        summary: 'Record what the tablet shows the way published editions do.',
        steps: [
          'Select a sign and, under Reading, choose Uncertain.',
          'For a sign lost on the tablet and restored by the editor, choose Lost, restored.',
          'Tick “A word ends after this sign” where a word ends (or press W).',
          'Save: the transliteration shows ka-ụ-[de] ta. The dot marks an uncertain sign, the brackets a restored one.',
        ],
        tryIt: { to: '/tablets/HT-13', label: 'Open a tablet' },
      },
      {
        id: 'work-faster',
        title: 'Work faster in the editor',
        summary: 'Zoom, invert faint drawings and use the keyboard.',
        steps: [
          'Zoom in on small signs; drag with the space bar held to pan.',
          'Invert the drawing when strokes are hard to see.',
          'N and P move between signs; press ? for every shortcut.',
        ],
        tryIt: { to: '/tablets/HT-13', label: 'Open the editor' },
      },
    ],
  },
  {
    title: 'Build editions',
    lessons: [
      {
        id: 'compare-versions',
        title: 'Compare versions',
        summary: 'See where the scholars, the reader and your colleagues agree and differ.',
        steps: [
          'On a tablet, tick two or more versions and choose Compare.',
          'Each version has its own colour; the summary shows how often they agree.',
          'Show only the differences and click one to find it on the tablet.',
        ],
        tryIt: { to: '/tablets/HT-13', label: 'Compare on HT 13' },
      },
      {
        id: 'merge-an-edition',
        title: 'Merge an edition',
        summary: 'Combine the best readings of several versions into one edition.',
        steps: [
          'From a comparison, choose Merge into an edition.',
          'Where versions disagree, pick whose sign to keep; agreements are kept for you.',
          'The edition opens in the editor, and every box remembers whose it was.',
        ],
        tryIt: { to: '/tablets/HT-13', label: 'Start on HT 13' },
      },
      {
        id: 'release-and-vote',
        title: 'Release and vote',
        summary: 'Share a finished edition and help the community agree on one.',
        steps: [
          'Release an edition when it is ready: a release never changes.',
          'On the tablet, back the release you think is best, one vote per tablet.',
          'The most-backed release becomes the community edition.',
        ],
        tryIt: { to: '/tablets/HT-13', label: 'See HT 13’s editions' },
      },
      {
        id: 'cite-and-export',
        title: 'Cite and export',
        summary: 'Cite a release in your work and download it in standard formats.',
        steps: [
          'Every release has a permanent page to cite.',
          'Copy the ready-made citation.',
          'Download it as TEI-EpiDoc, SVG, PNG, CSV or JSON.',
        ],
        tryIt: { to: '/editions/1', label: 'Open a release' },
      },
    ],
  },
  {
    title: 'Work together',
    lessons: [
      {
        id: 'discuss',
        title: 'Discuss a reading',
        summary: 'Talk through doubtful signs with colleagues.',
        steps: [
          'Signs, glyphs and editions list the discussions that mention them.',
          'Type @ to mention a colleague, a sign or an edition.',
          'Whoever you mention gets a notification.',
        ],
        tryIt: { to: '/community', label: 'Open Community' },
      },
      {
        id: 'stay-up-to-date',
        title: 'Stay up to date',
        summary: 'Notifications and activity bubbles show what changed.',
        steps: [
          'The bell collects shares, replies, mentions and votes.',
          'Click a notification to go straight to it.',
          'Activity bubbles, from your account menu, mark signs with news.',
        ],
        tryIt: { to: '/tablets/HT-13', label: 'Open a tablet' },
      },
      {
        id: 'search-sequences',
        title: 'Search sign sequences',
        summary: 'Find every tablet with a word or formula, such as KU-RO.',
        steps: [
          'On Tablets, switch the search to Sign sequence.',
          'Use readings or sign numbers; * matches any one sign.',
          'Open a result and the matches are highlighted.',
        ],
        tryIt: { to: '/tablets', label: 'Search the corpus' },
      },
      {
        id: 'find-work',
        title: 'Find where to help',
        summary: 'Work queues list the tablets and signs that most need attention.',
        steps: [
          'Most disagreement: tablets where readings differ most.',
          'Low-confidence signs: where the reader is unsure.',
          'No edition yet: tablets waiting for an edition.',
          'Each row opens the page where you can act.',
        ],
        tryIt: { to: '/queues', label: 'Open work queues' },
      },
    ],
  },
]

export const LESSONS = SECTIONS.flatMap((section) =>
  section.lessons.map((lesson) => ({ ...lesson, section: section.title })),
)

export const videoUrl = (lesson) => `/tutorials/${lesson.id}.mp4`
export const posterUrl = (lesson) => `/tutorials/${lesson.id}.jpg`

// Which lessons this browser has watched: a convenience only, so it may be forgotten.
const KEY = 'ase3.tutorials-watched'

function read() {
  try {
    const saved = JSON.parse(localStorage.getItem(KEY) ?? '[]')
    return Array.isArray(saved)
      ? saved.filter((id) => LESSONS.some((lesson) => lesson.id === id))
      : []
  } catch {
    return []
  }
}

export const WATCHED = ref(read())

watch(
  WATCHED,
  (ids) => {
    try {
      localStorage.setItem(KEY, JSON.stringify(ids))
    } catch {
      // Not remembered; the page works the same.
    }
  },
  { deep: true },
)

export function markWatched(id) {
  if (!WATCHED.value.includes(id)) WATCHED.value = [...WATCHED.value, id]
}

// The welcome on the home page, until dismissed.
const WELCOME_KEY = 'ase3.welcome-dismissed'

function readWelcome() {
  try {
    return localStorage.getItem(WELCOME_KEY) === '1'
  } catch {
    return false
  }
}

export const WELCOME_DISMISSED = ref(readWelcome())

export function dismissWelcome() {
  WELCOME_DISMISSED.value = true
  try {
    localStorage.setItem(WELCOME_KEY, '1')
  } catch {
    // Shown again next time; harmless.
  }
}
