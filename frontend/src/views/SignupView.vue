<script setup>
import { useAuth } from '../composables/useAuth'

const { username, email, password, pending, error, submit } = useAuth('register')
</script>

<template>
  <main class="px-4 pt-20">
    <form class="mx-auto flex max-w-sm flex-col gap-3 rounded-3xl bg-card p-6" :aria-busy="pending" @submit.prevent="submit">
      <h1 class="text-center text-4xl font-black uppercase">SIGNUP</h1>

      <input
        v-model="username"
        name="username"
        aria-label="Username"
        :disabled="pending"
        type="text"
        placeholder="Username"
        autocomplete="username"
        maxlength="255"
        pattern=".*\S.*"
        required
        class="w-full rounded-lg bg-page px-3 py-2 placeholder:text-ink/40 focus:outline-2 focus:outline-accent"
      />

      <input
        v-model="email"
        autocomplete="email"
        name="email"
        aria-label="Email"
        :disabled="pending"
        type="email"
        placeholder="Email"
        required
        class="w-full rounded-lg bg-page px-3 py-2 placeholder:text-ink/40 focus:outline-2 focus:outline-accent"
      />
      
      <input
        v-model="password"
        name="password"
        aria-label="Password"
        :disabled="pending"
        type="password"
        placeholder="Password"
        autocomplete="new-password"
        required
        class="w-full rounded-lg bg-page px-3 py-2 placeholder:text-ink/40 focus:outline-2 focus:outline-accent"
      />

      <p v-if="error" role="alert">{{ error }}</p>

      <button :disabled="pending" type="submit" class="mx-auto cursor-pointer rounded bg-bar px-8 py-1.5 hover:brightness-75">
        Sign Up
      </button>
    </form>
  </main>
</template>