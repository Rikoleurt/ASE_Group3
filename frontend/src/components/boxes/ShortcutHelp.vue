<script setup>
// The editor's keyboard shortcuts (workbench, story K), opened with ? and closed with Escape.
defineEmits(['close'])

const SHORTCUTS = [
  ['N / P', 'Next / previous box, in reading order'],
  ['V / D', 'Select and move / draw a box'],
  ['1 – 5', "Name the selected box with the model's guess 1 to 5"],
  ['U', 'Mark the selected box uncertain, or certain again'],
  ['W', 'A word ends after the selected box, or not'],
  ['Arrows', 'Move the selected box; with Shift, resize it'],
  ['Delete', 'Delete the selected box'],
  ['+ / − / 0', 'Zoom in / out / fit'],
  ['Space + drag', 'Pan the zoomed tablet'],
  ['Ctrl + Z', 'Undo your last unsaved edit'],
  ['Ctrl + S', 'Save'],
  ['?', 'Show or hide this list'],
]
</script>

<template>
  <div
    class="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4"
    data-testid="shortcut-help"
    @click.self="$emit('close')"
  >
    <section
      class="max-h-[90vh] w-full max-w-lg overflow-auto rounded-2xl bg-page p-6 shadow-xl"
      role="dialog"
      aria-modal="true"
      aria-labelledby="shortcuts-h"
    >
      <div class="flex items-start justify-between gap-4">
        <h2 id="shortcuts-h" class="text-xl font-bold">Keyboard shortcuts</h2>
        <button type="button" class="cursor-pointer text-sm underline" @click="$emit('close')">
          Close
        </button>
      </div>
      <table class="mt-3 w-full text-sm">
        <tbody>
          <tr v-for="[keys, does] in SHORTCUTS" :key="keys" class="border-t border-ink/10">
            <th scope="row" class="py-1.5 pr-4 text-left font-mono whitespace-nowrap">
              {{ keys }}
            </th>
            <td class="py-1.5">{{ does }}</td>
          </tr>
        </tbody>
      </table>
      <p class="mt-3 text-xs text-ink/80">Shortcuts do nothing while you type in a field.</p>
    </section>
  </div>
</template>
