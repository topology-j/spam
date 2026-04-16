<template>
  <div>
    <h2>Chat</h2>

    <div style="height:300px; overflow:auto;">
      <div v-for="(h, i) in history" :key="i">
        <b>{{ h.role }}</b>: {{ h.message }}
      </div>
    </div>

    <input v-model="message" />
    <button @click="send">전송</button>
  </div>
</template>

<script>
import api from "../api";

export default {
  data() {
    return {
      message: "",
      history: [],
    };
  },

  async mounted() {
    const res = await api.get("/chat/history");
    this.history = res.data;
  },

  methods: {
    async send() {
      if (!this.message) return;

      const res = await api.post("/chat", {
        message: this.message,
      });

      this.history.push(
        { role: "user", message: this.message },
        { role: "ai", message: res.data.reply }
      );

      this.message = "";
    },
  },
};
</script>