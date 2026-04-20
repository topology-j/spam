<script setup>
import { ref } from 'vue'
import { RouterView } from 'vue-router'

const playing = ref(false)
const volume = ref(30)

let player = null
let playerReady = false

function initYT() {
  if (window.YT && window.YT.Player) {
    createPlayer()
  } else {
    const tag = document.createElement('script')
    tag.src = 'https://www.youtube.com/iframe_api'
    document.head.appendChild(tag)
    window.onYouTubeIframeAPIReady = createPlayer
  }
}

function createPlayer() {
  player = new window.YT.Player('yt-player', {
    videoId: 'jQTdfThmwIs',
    playerVars: { autoplay: 0, loop: 1, playlist: 'jQTdfThmwIs', controls: 0 },
    events: {
      onReady: () => {
        playerReady = true
        player.mute()
        player.playVideo()
        setTimeout(() => {
          player.unMute()
          player.setVolume(volume.value)
        }, 500)
      },
    },
  })
}

function togglePlay() {
  if (!player || !playerReady) { initYT(); playing.value = true; return }
  if (playing.value) {
    player.pauseVideo()
  } else {
    player.playVideo()
  }
  playing.value = !playing.value
}

function onVolumeChange() {
  if (player) player.setVolume(volume.value)
}
</script>

<template>
  <RouterView />

  <div id="yt-player" style="display:none" />

  <div class="music-bar">
    <button class="music-btn" @click="togglePlay" :title="playing ? '일시정지' : '재생'">
      <svg v-if="!playing" width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
        <polygon points="5,3 19,12 5,21"/>
      </svg>
      <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
        <rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/>
      </svg>
    </button>
    <div class="music-info">
      <span class="music-title">Viva la Vida</span>
      <span class="music-artist">Freedom Orchestra</span>
    </div>
    <input
      type="range" min="0" max="100" v-model="volume"
      class="music-vol" @input="onVolumeChange"
    />
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" opacity="0.6">
      <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>
      <path d="M19.07 4.93a10 10 0 0 1 0 14.14"/>
      <path d="M15.54 8.46a5 5 0 0 1 0 7.07"/>
    </svg>
  </div>
</template>

<style>
.music-bar {
  position: fixed;
  bottom: 20px;
  right: 20px;
  display: flex;
  align-items: center;
  gap: 10px;
  background: rgba(19, 17, 28, 0.92);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 999px;
  padding: 8px 16px 8px 10px;
  z-index: 9999;
  color: #fff;
  box-shadow: 0 8px 32px rgba(0,0,0,0.4);
}
.music-btn {
  width: 32px; height: 32px;
  border-radius: 50%;
  background: #6366f1;
  border: none; cursor: pointer;
  color: #fff;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.music-btn:hover { background: #4f46e5; }
.music-info {
  display: flex; flex-direction: column; gap: 1px;
  min-width: 90px;
}
.music-title { font-size: 12px; font-weight: 700; color: #fff; white-space: nowrap; }
.music-artist { font-size: 10px; color: #9ca3af; }
.music-vol {
  width: 70px;
  accent-color: #6366f1;
  cursor: pointer;
}
</style>
