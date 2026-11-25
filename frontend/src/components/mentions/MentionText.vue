<script setup>
import { computed } from 'vue'
import { parseMentionTokens } from './mentionSyntax'

const props = defineProps({ body: { type: String, required: true }, mentions: { type: Array, default: () => [] } })
defineEmits(['preview'])
const parts = computed(() => {
  const resolved = new Map(props.mentions.map((mention) => [mention.token, mention]))
  const result = []
  let offset = 0
  for (const token of parseMentionTokens(props.body)) {
    result.push({ text: props.body.slice(offset, token.start) })
    const mention = resolved.get(token.token)
    result.push(mention ? { mention } : { text: token.token })
    offset = token.end
  }
  result.push({ text: props.body.slice(offset) })
  return result
})
</script>

<template>
  <p class="whitespace-pre-wrap break-words"><template v-for="(part, index) in parts" :key="index"><template v-if="!part.mention">{{ part.text }}</template><span v-else-if="!part.mention.available" class="text-ink/60" title="This mention is no longer available">@{{ part.mention.label }}</span><RouterLink v-else-if="part.mention.kind === 'user'" :to="{ path: '/community', query: { filter_by: 'author', author_id: String(part.mention.user_id) } }" class="rounded bg-ink/10 px-1 font-semibold hover:underline">@{{ part.mention.label }}</RouterLink><button v-else type="button" class="cursor-pointer rounded bg-ink/10 px-1 font-semibold hover:underline" @click="$emit('preview', part.mention)">@{{ part.mention.label }}</button></template></p>
</template>
