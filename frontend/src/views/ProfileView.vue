<script setup>

// Placeholders until we have implemented a session of some kind
const user = {
  name: 'Testname',
  email: 'testmail@test.com',
  avatar: '',
  details: [
    { label: 'Username', value: 'Test' },
    { label: 'Email', value: 'testmail@test.com' },
    { label: 'Symbols clustered', value: '18' },
  ],
}

function logout() {
  console.log('logout')
}
</script>

<template>
  <main class="px-4 pt-10 pb-10">
    <section
      class="mx-auto flex max-w-4xl flex-col items-center gap-8 rounded-3xl bg-card p-8 sm:flex-row sm:items-start sm:gap-12 sm:p-10"
    >
   
      <div class="h-48 w-48 shrink-0 overflow-hidden rounded-full ring-4 ring-bar">
        <img
          v-if="user.avatar"
          :src="user.avatar"
          alt=""
          class="h-full w-full object-cover"
        />
        <span v-else class="block h-full w-full bg-bar" />
      </div>

      <div class="w-full min-w-0 text-center sm:text-left">
        <h1 class="text-3xl font-bold">{{ user.name }}</h1>

        <dl class="mt-6 divide-y divide-ink/10 text-left">
          <div
            v-for="item in user.details"
            :key="item.label"
            class="flex justify-between gap-4 py-2"
          >
            <dt class="text-ink/70">{{ item.label }}</dt>
            <dd class="font-medium">{{ item.value }}</dd>
          </div>
        </dl>

        <div class="mt-8 flex justify-center gap-3 sm:justify-start">
          <button
            type="button"
            class="mx-auto cursor-pointer rounded bg-bar px-8 py-1.5 hover:brightness-75"
            @click="logout"
          >
            Log out
          </button>
        </div>
      </div>
    </section>
  </main>
</template>