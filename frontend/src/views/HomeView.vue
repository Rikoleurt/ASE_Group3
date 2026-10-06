<template>
  <main class="mx-auto flex max-w-3xl flex-col items-center gap-16 px-6 py-16 text-center">
    
    <section class="flex flex-col items-center gap-6">
      <h1 class="text-5xl font-light sm:text-7xl">Lorem Ipsum</h1>
      <p class="max-w-2xl text-base leading-relaxed sm:text-lg">
        Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor
        incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud
        exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure
        dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur.
        Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt
        mollit anim id est laborum.
      </p>

      <RouterLink
        to="/tablet-demo"
        class="rounded bg-bar px-8 py-2 font-medium shadow-sm hover:brightness-95 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent">
        Check out the Demo
      </RouterLink>
    </section>

    <section class="flex flex-col items-center gap-3">
      <h2 class="text-xl font-bold">How does it work?</h2>
      <p class="max-w-2xl leading-relaxed">
        Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor
        incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud
        exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.
      </p>
    </section>
  </main>
</template>