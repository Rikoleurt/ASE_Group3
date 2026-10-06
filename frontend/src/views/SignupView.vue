<script setup>
  import { ref } from 'vue'

  const username = ref('')
  const password = ref('')

  // Todo for now until backend points exist
  function submit() {
    console.log('signup', { username: username.value, email: email.value, password: password.value })
  }
</script>

<template>
  <main class="px-4 pt-20">
    <form class="mx-auto flex max-w-sm flex-col gap-3 rounded-3xl bg-card p-6" @submit.prevent="submit">
      <h1 class="text-center text-4xl font-black uppercase">SIGNUP</h1>

      <input
        v-model="username"
        type="text"
        placeholder="Username"
        autocomplete="username"
        required
        class="w-full rounded-lg bg-page px-3 py-2 placeholder:text-ink/40 focus:outline-2 focus:outline-accent"
      />

      <input
        v-model="email"
        type="text"
        placeholder="Email"
        required
        class="w-full rounded-lg bg-page px-3 py-2 placeholder:text-ink/40 focus:outline-2 focus:outline-accent"
      />
      
      <input
        v-model="password"
        type="password"
        placeholder="Password"
        required
        class="w-full rounded-lg bg-page px-3 py-2 placeholder:text-ink/40 focus:outline-2 focus:outline-accent"
      />

      <button type="submit" class="mx-auto cursor-pointer rounded bg-bar px-8 py-1.5 hover:brightness-75">
        Sign Up
      </button>
    </form>
  </main>
</template>