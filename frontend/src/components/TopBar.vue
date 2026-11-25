<script setup>
// The top bar: the main pages in one row, the two HT 13 demo pages under "Demos", and
// everything about your account (shared copies, review, admin, profile, log out) under the
// profile button, so the bar fits on one line.
import { SHOW_ACTIVITY } from '../state/preferences'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { loadSession, logoutSession, sessionAdmin, sessionReviewer, sessionUser } from '../state/session'

const route = useRoute()
const router = useRouter()
const loggingOut = ref(false)
const logoutError = ref('')
const OPEN = ref(null) // 'demos', 'account' or null
const BAR = ref(null)

onMounted(() => loadSession().catch(() => {}))

async function logout() {
    if (loggingOut.value) return
    loggingOut.value = true
    logoutError.value = ''
    try {
        await logoutSession()
        OPEN.value = null
        await router.push('/login')
    } catch {
        logoutError.value = 'Unable to log out. Please try again.'
    } finally {
        loggingOut.value = false
    }
}

function toggle(menu) {
    OPEN.value = OPEN.value === menu ? null : menu
}

// A menu closes on a click elsewhere, on Escape, and when the page changes.
function closeOutside(event) {
    if (OPEN.value && !BAR.value?.contains(event.target)) OPEN.value = null
}
function closeOnEscape(event) {
    if (event.key === 'Escape') OPEN.value = null
}
onMounted(() => {
    document.addEventListener('click', closeOutside)
    document.addEventListener('keydown', closeOnEscape)
})
onBeforeUnmount(() => {
    document.removeEventListener('click', closeOutside)
    document.removeEventListener('keydown', closeOnEscape)
})
watch(() => route.fullPath, () => { OPEN.value = null })

const avatarUrl = ''
const pageLinks = [
    {to: '/', label: 'Home', icon: 'home'},
    {to: '/analysis', label: 'Analysis', icon: 'search'},
    {to: '/tablets', label: 'Tablets', icon: 'book'},
    {to: '/signs', label: 'Signs', icon: 'pen'},
    {to: '/community', label: 'Community', icon: 'lines'},
    {to: '/benchmarks', label: 'Benchmarks', icon: 'chart'},
]
const demoLinks = [
    {to: '/tablet-demo', label: 'Tablet demo (HT 13)'},
    {to: '/tablet-reading', label: 'Tablet reading (HT 13)'},
]

const linkClass = 'inline-flex items-center gap-1.5 whitespace-nowrap hover:underline focus-visible:underline'
const activeClass = 'font-bold underline'
const menuClass = 'absolute right-0 top-full z-40 mt-2 min-w-48 rounded-xl bg-card py-2 shadow-lg ring-1 ring-ink/10'
const itemClass = 'block whitespace-nowrap px-4 py-1.5 hover:bg-bar focus-visible:bg-bar'
</script>

<template>
    <header ref="BAR" class="flex min-h-[60px] items-center justify-between gap-4 bg-bar px-5 py-2 text-ink">
        <nav class="flex min-w-0 flex-wrap items-center gap-x-5 gap-y-2" aria-label="Main">
            <RouterLink v-for="link in pageLinks"
                :key="link.to"
                :to="link.to"
                :class="linkClass"
                :exact-active-class="link.to === '/' ? activeClass : undefined"
                :active-class="link.to === '/' ? undefined : activeClass">

                <svg v-if="link.icon === 'home'" class="h-5 w-5 shrink-0" viewBox="0 0 24 24" aria-hidden="true">
                    <path fill="currentColor" d="M12 3 1.5 12.5H5V21h5.5v-6h3v6H19v-8.5h3.5z" />
                </svg>
                <svg v-else-if="link.icon === 'pen'" class="h-5 w-5 shrink-0" viewBox="0 0 24 24" aria-hidden="true">
                    <path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" d="M4 20l4-1 11-11-3-3L5 16l-1 4zM14 6l3 3" />
                </svg>
                <svg v-else-if="link.icon === 'book'" class="h-5 w-5 shrink-0" viewBox="0 0 24 24" aria-hidden="true">
                    <path fill="currentColor" fill-rule="evenodd" d="M6 2h13a1 1 0 0 1 1 1v18a1 1 0 0 1-1 1H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2Zm3 4v2.5h7V6Z" />
                </svg>
                <svg v-else-if="link.icon === 'lines'" class="h-5 w-5 shrink-0" viewBox="0 0 24 24" aria-hidden="true">
                    <path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" d="M4 6h16M4 12h10M4 18h13" />
                </svg>
                <svg v-else-if="link.icon === 'search'" class="h-5 w-5 shrink-0" viewBox="0 0 24 24" aria-hidden="true">
                    <circle cx="10.8" cy="10.8" r="7" fill="none" stroke="currentColor" stroke-width="2" />
                    <path d="m16 16 5 5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
                </svg>
                <svg v-else class="h-5 w-5 shrink-0" viewBox="0 0 24 24" aria-hidden="true">
                    <path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" d="M3 3v18h18M7 15l4-5 3 3 5-7" />
                </svg>

                <!-- The bold copy reserves the width, so the bar does not shift when a link becomes active. -->
                <span class="grid">
                    <span class="invisible col-start-1 row-start-1 font-bold" aria-hidden="true">{{ link.label }}</span>
                    <span class="col-start-1 row-start-1">{{ link.label }}</span>
                </span>
            </RouterLink>

            <div class="relative">
                <button
                    type="button"
                    :class="[linkClass, 'cursor-pointer', { 'font-bold underline': demoLinks.some((link) => route.path === link.to) }]"
                    :aria-expanded="OPEN === 'demos'"
                    aria-haspopup="true"
                    data-testid="demos-menu"
                    @click="toggle('demos')">
                    Demos <span aria-hidden="true">▾</span>
                </button>
                <div v-show="OPEN === 'demos'" :class="[menuClass, 'left-0 right-auto']">
                    <RouterLink v-for="link in demoLinks" :key="link.to" :to="link.to" :class="itemClass" exact-active-class="font-bold">
                        {{ link.label }}
                    </RouterLink>
                </div>
            </div>
        </nav>

        <div class="flex shrink-0 items-center gap-4">
            <p v-if="logoutError" role="alert">{{ logoutError }}</p>
            <template v-if="!sessionUser">
                <RouterLink to="/login" :class="linkClass" exact-active-class="font-bold underline">Log in</RouterLink>
                <RouterLink to="/signup" :class="linkClass" exact-active-class="font-bold underline">Sign up</RouterLink>
            </template>

            <div v-else class="relative">
                <button
                    type="button"
                    class="flex cursor-pointer items-center gap-2 rounded-full pr-1 hover:underline focus-visible:outline-2 focus-visible:outline-accent"
                    :aria-expanded="OPEN === 'account'"
                    aria-haspopup="true"
                    :aria-label="`Account menu for ${sessionUser.username}`"
                    data-testid="account-menu"
                    @click="toggle('account')">
                    <span class="block h-10 w-10 overflow-hidden rounded-full bg-card">
                        <!-- TODO: Do we want profile pictures to fetch from be or just have a placeholder? -->
                        <img v-if="avatarUrl" :src="avatarUrl" alt="" class="h-full w-full object-cover" />
                    </span>
                    <span class="hidden whitespace-nowrap sm:inline">{{ sessionUser.username }}</span>
                    <span aria-hidden="true">▾</span>
                </button>
                <div v-show="OPEN === 'account'" :class="menuClass">
                    <RouterLink to="/profile" :class="itemClass" exact-active-class="font-bold">Profile</RouterLink>
                    <RouterLink to="/shared" :class="itemClass" exact-active-class="font-bold">Shared with me</RouterLink>
                    <RouterLink v-if="sessionReviewer" to="/review" :class="itemClass" exact-active-class="font-bold">Review corrections</RouterLink>
                    <RouterLink v-if="sessionAdmin" to="/admin" :class="itemClass" exact-active-class="font-bold">Admin</RouterLink>
                    <label :class="[itemClass, 'flex cursor-pointer items-center gap-2 border-t border-ink/10']" data-testid="activity-toggle">
                        <input v-model="SHOW_ACTIVITY" type="checkbox" class="h-4 w-4" />
                        Show activity on glyphs
                    </label>
                    <button
                        type="button"
                        :class="[itemClass, 'w-full cursor-pointer border-t border-ink/10 text-left disabled:cursor-wait']"
                        :disabled="loggingOut"
                        data-testid="logout"
                        @click="logout">
                        {{ loggingOut ? 'Logging out…' : 'Log out' }}
                    </button>
                </div>
            </div>
        </div>
    </header>
</template>
