<template>
  <div>
    <h2>Login</h2>

    <input v-model="username" placeholder="username" />
    <input v-model="password" type="password" placeholder="password" />

    <button @click="login">로그인</button>

    <p v-if="error" style="color:red">{{ error }}</p>
  </div>
</template>

<script>
import api from "../api";

export default {
  data() {
    return {
      username: "",
      password: "",
      error: "",
    };
  },

  methods: {
    async login() {
      this.error = "";

      try {
        const res = await api.post("/auth/login", {
          username: this.username,
          password: this.password,
        });

        localStorage.setItem("token", res.data.token);
        localStorage.setItem("role", res.data.role);
        localStorage.setItem("username", res.data.username);

        alert("로그인 성공");

        // 필요하면 이동
        // this.$router.push("/home");

      } catch (err) {
        console.log(err);
        this.error = "로그인 실패";
      }
    },
  },
};
</script>