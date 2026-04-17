<template>
  <div>
    <h2>Spam Report</h2>

    <textarea v-model="email"></textarea>
    <button @click="submit">신고</button>

    <div v-for="r in reports" :key="r.id">
      <p>{{ r.email_content }}</p>
      <p>{{ r.status }}</p>
    </div>
  </div>
</template>

<script>
import api from "../api";

export default {
  data() {
    return {
      email: "",
      reports: [],
    };
  },

  async mounted() {
    this.load();
  },

  methods: {
    async load() {
      const res = await api.get("/spam-reports/my");
      this.reports = res.data;
    },

    async submit() {
      await api.post("/spam-reports", {
        email_content: this.email,
      });

      this.email = "";
      this.load();
    },
  },
};
</script>