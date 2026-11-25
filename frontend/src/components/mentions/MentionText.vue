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
  <p class="whitespace-pre-wrap break-words"><template v-for="(part, index) in parts" :key="index"><template v-if="!part.mention">{{ part.text }}</template><span v-else-if="!part.mention.available" class="text-ink/60" title="This mention is no longer available">@{{ part.mention.label }}</span><span v-else-if="part.mention.kind === 'sign'" class="inline-flex items-center gap-1 rounded bg-ink/10 px-1 align-bottom font-semibold" data-testid="sign-mention"><img v-if="part.mention.image_url" :src="part.mention.image_url" alt="" class="h-5 w-5 rounded-sm bg-white object-contain" />@{{ part.mention.label }}</span><RouterLink v-else-if="part.mention.kind === 'glyph'" :to="`/tablets/${part.mention.glyph_tablet}`" class="inline-flex items-center gap-1 rounded bg-ink/10 px-1 align-bottom font-semibold hover:underline" data-testid="glyph-mention"><img v-if="part.mention.image_url" :src="part.mention.image_url" alt="" class="h-5 w-8 rounded-sm bg-white object-contain" />@{{ part.mention.label }}</RouterLink><RouterLink v-else-if="part.mention.kind === 'edition'" :to="`/editions/${part.mention.release_id}`" class="rounded bg-ink/10 px-1 font-semibold hover:underline" data-testid="edition-mention">@{{ part.mention.label }}</RouterLink><RouterLink v-else-if="part.mention.kind === 'user'" :to="{ path: '/community', query: { filter_by: 'author', author_id: String(part.mention.user_id) } }" class="rounded bg-ink/10 px-1 font-semibold hover:underline">@{{ part.mention.label }}</RouterLink><button v-else type="button" class="cursor-pointer rounded bg-ink/10 px-1 font-semibold hover:underline" @click="$emit('preview', part.mention)">@{{ part.mention.label }}</button></template></p>
</template>
