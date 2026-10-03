<template><main class="presentation-layout"><slot /></main></template>
<style scoped>
.presentation-layout { min-height: 100vh; padding: 26px 36px; background: radial-gradient(ellipse at top,#eaf1ff,#f5f8fd 65%); }
@media(max-width:600px) { .presentation-layout { padding: 18px 12px; } }
</style>
