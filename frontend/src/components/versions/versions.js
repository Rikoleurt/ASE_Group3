// Names and colours for the versions of a tablet (workbench): the scholars', the model's, copies.

// Okabe-Ito colours: distinguishable with the common colour-vision deficiencies.
export const VERSION_COLOURS = ['#0072B2', '#D55E00', '#009E73', '#CC79A7', '#E69F00', '#56B4E9']

export function versionName(version) {
  if (version.kind === 'scholar') return "Scholars' boxes"
  if (version.kind === 'model') return "Model's boxes"
  const whose = version.mine ? 'Your' : `${version.owner}'s`
  const what = version.kind === 'edition' ? 'edition' : 'copy'
  return version.title ? `${whose} ${what}: ${version.title}` : `${whose} ${what}`
}

export const STATUS_LABELS = {
  agree: 'Agree',
  differs: 'Different signs',
  missing: 'Missing from some',
}
