<script setup>
const avatarUrl = ''
const pageLinks = [
    {to: '/', label: 'Home', icon: 'home'},
    {to: '/tablet-demo', label: 'Tablet Demo', icon: 'book'},
    {to: '/cluster', label: 'Cluster', icon: 'chart'},
]
const userLinks = [
    {to: '/login', label: 'Login'},
    {to: '/signup', label: 'Signup'}
]

const linkClass = 'inline-flex items-center gap-2 text-[1.05rem] hover:underline focus-visible:underline'
const activeClass = 'font-bold underline'

</script>

<template>
    <header class="flex h-[60px] items-center justify-between bg-bar px-5 text-ink">
        <nav class="flex items-center gap-6">
            <RouterLink v-for="link in pageLinks"
                :key="link.to"
                :to="link.to"
                :class="linkClass"
                :exact-active-class="activeClass">
            
            <svg v-if="link.icon === 'home'" class="h-6 w-6" viewBox="0 0 24 24">
                <path fill="currentColor" d="M12 3 1.5 12.5H5V21h5.5v-6h3v6H19v-8.5h3.5z" />
            </svg>

            <svg v-else-if="link.icon === 'book'" class="h-6 w-6" viewBox="0 0 24 24">
                <path
                    fill="currentColor"
                    fill-rule="evenodd"
                    d="M6 2h13a1 1 0 0 1 1 1v18a1 1 0 0 1-1 1H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2Zm3 4v2.5h7V6Z"
                />
            </svg>

            <svg v-else class="h-6 w-6" viewBox="0 0 24 24">
                <path
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    d="M3 3v18h18M7 15l4-5 3 3 5-7"
                />
            </svg>

            <span>{{ link.label }}</span>
            </RouterLink>

        </nav>

        <div class="flex items-center gap-6">
            <RouterLink
                v-for="link in userLinks"
                :key="link.to"
                :to="link.to"
                :class="linkClass"
                :exact-active-class="activeClass">
                {{ link.label }}
            </RouterLink>
 
            <RouterLink
                to="/profile"
                aria-label="Profile"
                class="block h-[52px] w-[52px] overflow-hidden rounded-full hover:ring-2 hover:ring-accent focus-visible:ring-2 focus-visible:ring-accent"
                exact-active-class="ring-2 ring-accent">
                <!-- TODO: Do we want profile pictures to fetch from be or just have a placeholder? -->
                <img v-if="avatarUrl" :src="avatarUrl" class="h-full w-full object-cover"/>
                <span v-else class="block h-full w-full bg-card" />
            </RouterLink>
        </div>
    </header>
</template>
