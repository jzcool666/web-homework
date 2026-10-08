<script setup>
import { onMounted, ref } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";
import { api, ApiError } from "@/api/client";
import { newLabKey } from "@/utils/lab";
import PageHeader from "@/components/ui/PageHeader.vue";
import SectionCard from "@/components/ui/SectionCard.vue";
import StatePanel from "@/components/ui/StatePanel.vue";
const route = useRoute();
const router = useRouter();
const task = ref(null);
const classes = ref([]);
const classId = ref("");
const file = ref(null);
const error = ref("");
const busy = ref(false);
const requestKey = ref(null);
async function load() {
  try {
    const [definition, rows] = await Promise.all([
      api.get(`/lab-tasks/${route.params.id}`),
      api.get("/classes?page_size=100"),
    ]);
    task.value = definition;
    classes.value = rows.filter((item) => item.active);
    classId.value = classes.value.some(
      (item) => String(item.id) === route.query.class_id,
    )
      ? route.query.class_id
      : (classes.value[0]?.id ?? "");
  } catch (err) {
    error.value = err.message;
  }
}
function select(event) {
  file.value = event.target.files?.[0] ?? null;
  requestKey.value = null;
  error.value = "";
}
async function submit() {
  if (busy.value || !file.value || !classId.value) return;
  if (!file.value.name.toLowerCase().endsWith(".circ")) {
    error.value = "请选择.circ电路文件";
    return;
  }
  if (file.value.size > 2 * 1024 * 1024) {
    error.value = "文件不能超过2MiB";
    return;
  }
  busy.value = true;
  error.value = "";
  requestKey.value ??= newLabKey();
  const body = new FormData();
  body.set("file", file.value);
  body.set("task_id", String(task.value.id));
  body.set("task_version", String(task.value.version));
  body.set("class_id", String(classId.value));
  body.set("request_key", requestKey.value);
  try {
    const row = await api.postForm("/lab-attempts/circ", body);
    requestKey.value = null;
    await router.push({ name: "lab-attempt", params: { id: row.id } });
  } catch (err) {
    error.value = err.message;
    if (err instanceof ApiError) requestKey.value = null;
    else
      error.value =
        "连接中断，提交是否接收尚未确认。请保持文件和班级不变，点击重试。";
  } finally {
    busy.value = false;
  }
}
onMounted(load);
</script>

<template>
  <div class="lab-upload">
    <PageHeader icon="flask" :steps="['核对文件端口', '上传电路', '等待测评与首错']"
      :title="`${task?.title || '实验'} · 上传电路`"
      description="用 Logisim-evolution 5.0.0 设计电路，保存为.circ文件，由真实仿真引擎按多拍输入测评。"
    >
      <template #actions
        ><RouterLink class="button" :to="{ name: 'student-labs' }"
          >返回实验任务</RouterLink
        ></template
      >
    </PageHeader>
    <StatePanel
      v-if="!task"
      :kind="error ? 'error' : 'loading'"
      :title="error ? '任务无法读取' : '正在读取任务'"
      :description="error"
    />
    <template v-else>
      <SectionCard title="电路要求">
        <p>{{ task.instructions_md }}</p>
        <p>
          入口电路必须命名为
          <code>main</code
          >，以下端口名称、方向和位宽须完全一致。模板只有端口，不包含答案电路。
        </p>
        <div class="table-scroll">
          <table>
            <thead>
              <tr>
                <th>端口</th>
                <th>方向</th>
                <th>位宽</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="port in task.ports" :key="port.label">
                <td>{{ port.label }}</td>
                <td>{{ port.direction === "input" ? "输入" : "输出" }}</td>
                <td>{{ port.width }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <a class="button" :href="`/api/v1/lab-tasks/${task.id}/template`"
          >下载5.0.0端口模板</a
        >
        <details>
          <summary>支持范围</summary>
          <p>
            可用引脚、常量、分线器、Tunnel、探针、基础逻辑门、复用器、加减器、比较器、触发器、寄存器、计数器和任务对应TTL器件（7400/7404/7408/7432/7474/74161/74194）；允许本文件内无递归子电路。最多2MiB、16个电路、512个器件、2048条线。不支持外部库、HDL、RAM/ROM及文件组件。其他版本请先用5.0.0另存。
          </p>
        </details>
      </SectionCard>
      <SectionCard title="提交测评">
        <form @submit.prevent="submit">
          <label for="circ-class">班级</label
          ><select
            id="circ-class"
            v-model="classId"
            :disabled="busy || Boolean(requestKey)"
          >
            <option v-for="item in classes" :key="item.id" :value="item.id">
              {{ item.name }}
            </option>
          </select>
          <label for="circ-file">电路文件</label
          ><input
            id="circ-file"
            type="file"
            accept=".circ"
            :disabled="busy || Boolean(requestKey)"
            @change="select"
          />
          <p v-if="file">{{ file.name }} · {{ file.size }} 字节</p>
          <p class="hint">
            最多同时等待2个任务，两次上传至少间隔10秒。测评服务故障不计0分，可保留旧记录后重新提交。
          </p>
          <p v-if="error" class="error" role="alert">{{ error }}</p>
          <div class="form-actions"><button
            class="button button--primary"
            :disabled="busy || !file || !classId"
          >
            {{ busy ? "正在上传" : requestKey ? "重试上传" : "上传并测评" }}
          </button></div>
        </form>
      </SectionCard>
    </template>
  </div>
</template>

<style scoped>
.lab-upload {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 18px;
}
form {
  display: grid;
  gap: 12px;
  justify-items: start;
}
p {
  line-height: 1.7;
}
.error {
  color: #b42318;
}
table {
  width: 100%;
  margin-bottom: 16px;
}
th,
td {
  text-align: left;
  padding: 8px;
}
details {
  margin-top: 16px;
}
</style>
