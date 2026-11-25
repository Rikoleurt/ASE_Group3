<script setup>
// Draws several versions' boxes over the tablet in the slot, one colour per version. Each place
// (a cluster of matching boxes) can be clicked or focused to select it; the selected place is
// highlighted. Coordinates are fractions of the image.
import { computed } from 'vue'
import GlyphBadges from './GlyphBadges.vue'
import { VERSION_COLOURS } from './versions'

const props = defineProps({
  badges: { type: Object, default: () => ({}) }, // place index -> new activity (workbench)
  clusters: { type: Array, default: () => [] }, // [{ box, members: { key: { box, sign, label } }, status }]
  keys: { type: Array, default: () => [] }, // version keys, in colour order
  hidden: { type: Array, default: () => [] }, // version keys not drawn
  selected: { type: Number, default: null }, // index into clusters
})
const emit = defineEmits(['select'])
const BADGES = computed(() =>
  props.clusters
    .map((place, index) => ({ key: index, box: place.box, count: props.badges[index] }))
    .filter((item) => item.count),
)

const percent = (value) => value * 100
// Each version's box is drawn a little inside the previous one's, so boxes in the same place
// all stay visible: 0.35% of the image per version, at most a fifth of the box.
const inset = (colour, side) => Math.min(colour * 0.35, percent(side) / 5)
</script>

<template>
  <div class="relative">
    <slot />
    <svg
      class="absolute inset-0 h-full w-full"
      viewBox="0 0 100 100"
      preserveAspectRatio="none"
      data-testid="version-overlay"
    >
      <g
        v-for="(place, index) in clusters"
        :key="index"
        role="button"
        tabindex="0"
        class="cursor-pointer outline-none"
        :aria-label="`Place ${index + 1}`"
        :aria-pressed="selected === index"
        data-testid="place"
        @click="emit('select', index)"
        @keydown.enter.prevent="emit('select', index)"
        @keydown.space.prevent="emit('select', index)"
      >
        <rect
          v-if="selected === index"
          :x="percent(place.box.x) - 0.8"
          :y="percent(place.box.y) - 0.8"
          :width="percent(place.box.w) + 1.6"
          :height="percent(place.box.h) + 1.6"
          fill="rgba(250, 204, 21, 0.35)"
          stroke="none"
        />
        <template v-for="(key, colour) in keys" :key="key">
          <rect
            v-if="place.members[key] && !hidden.includes(key)"
            :x="percent(place.members[key].box.x) + inset(colour, place.members[key].box.w)"
            :y="percent(place.members[key].box.y) + inset(colour, place.members[key].box.h)"
            :width="
              Math.max(
                0.2,
                percent(place.members[key].box.w) - 2 * inset(colour, place.members[key].box.w),
              )
            "
            :height="
              Math.max(
                0.2,
                percent(place.members[key].box.h) - 2 * inset(colour, place.members[key].box.h),
              )
            "
            fill="transparent"
            :stroke="VERSION_COLOURS[colour % VERSION_COLOURS.length]"
            :stroke-dasharray="colour ? `${1 + colour} ${1}` : undefined"
            vector-effect="non-scaling-stroke"
            :stroke-width="selected === index ? 3 : 1.5"
            data-testid="version-box"
          />
        </template>
      </g>
    </svg>
    <GlyphBadges :items="BADGES" />
  </div>
</template>
