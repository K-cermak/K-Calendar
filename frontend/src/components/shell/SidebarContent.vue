<script setup lang="ts">
/** What the desktop sidebar and the phone drawer share: calendars and tags (SPEC 7). */
</script>

<template>
  <div class="flex flex-col gap-6 p-4">
    <section class="flex flex-col gap-2" data-testid="calendar-list">
      <h2 class="text-label font-medium text-muted">{{ $t('shell.calendars') }}</h2>
      <slot name="calendars" />
    </section>
    <section class="flex flex-col gap-2" data-testid="tag-list">
      <h2 class="text-label font-medium text-muted">{{ $t('shell.tags') }}</h2>
      <slot name="tags" />
    </section>
  </div>
</template>
