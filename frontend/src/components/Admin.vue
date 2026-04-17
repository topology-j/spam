<template>
  <div>
    <h2>Admin</h2>

    <h3>Reports</h3>
    <div v-for="r in reports" :key="r.id">
      <p>{{ r.email_content }}</p>
      <button @click="done(r.id)">완료</button>
    </div>

    <h3>Keywords</h3>
    <div v-for="k in keywords" :key="k.id">
      {{ k.keyword }}
      <button @click="remove(k.id)">삭제</button>
    </div>
  </div>
</template>

<script>
import api from "../api";

export default {
  data() {
    return {
      reports: [],
      keywords: [],
    };
  },

  async mounted() {
    this.load();
  },

  methods: {
    async load() {
      const r1 = await api.get("/spam-reports");
      const r2 = await api.get("/spam-keywords");

      this.reports = r1.data;
      this.keywords = r2.data;
    },

    async done(id) {
      await api.patch(`/spam-reports/${id}`, {
        status: "done",
        counselor_note: "처리 완료",
        keywords: [],
      });

      this.load();
    },

    async remove(id) {
      await api.delete(`/spam-keywords/${id}`);
      this.load();
    },
  },
};
</script>