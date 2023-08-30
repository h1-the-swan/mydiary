<template>
  <v-dialog v-model="dialog">
    <v-card>
      <v-card-title>
        <span class="text-h5">{{ formTitle }}</span>
      </v-card-title>

      <v-card-text>
        <v-container>
          <v-row>
            <v-col cols="12" sm="6" md="4">
              <v-text-field v-model="editedItem.name" label="Dessert name"></v-text-field>
            </v-col>
            <v-col cols="12" sm="6" md="4">
              <v-text-field v-model="editedItem.calories" label="Calories"></v-text-field>
            </v-col>
            <v-col cols="12" sm="6" md="4">
              <v-text-field v-model="editedItem.fat" label="Fat (g)"></v-text-field>
            </v-col>
            <v-col cols="12" sm="6" md="4">
              <v-text-field v-model="editedItem.carbs" label="Carbs (g)"></v-text-field>
            </v-col>
            <v-col cols="12" sm="6" md="4">
              <v-text-field v-model="editedItem.protein" label="Protein (g)"></v-text-field>
            </v-col>
          </v-row>
        </v-container>
      </v-card-text>

      <v-card-actions>
        <v-spacer></v-spacer>
        <v-btn color="blue-darken-1" variant="text" @click="close">
          Cancel
        </v-btn>
        <v-btn color="blue-darken-1" variant="text" @click="save">
          Save
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script lang="ts" setup>
import { toRefs } from 'vue';
import { computed, nextTick, ref, watch } from 'vue'
interface IDessert {
  name: string;
  calories: number;
  fat: number;
  carbs: number;
  protein: number;
}
interface IProps {
  dialog: boolean;
  editedIndex: number;
  editedItem: IDessert;
}
const props = defineProps<IProps>();
const emit = defineEmits(['save', 'update:dialog', 'update:editedItem', 'update:editedIndex', 'close']);
const { dialog, editedIndex, editedItem } = toRefs(props);
const formTitle = computed(() => {
  return editedIndex.value === -1 ? 'New Item' : 'Edit Item'
})
function save() {
  // if (editedIndex.value > -1) {
  //   Object.assign(desserts.value[editedIndex.value], editedItem.value)
  // } else {
  //   desserts.value.push(editedItem.value)
  // }
  emit('save');
  close();
}
function close() {
  emit('update:dialog', false);
  // nextTick(() => {
  //   editedItem.value = Object.assign({}, defaultItem.value)
  //   editedIndex.value = -1
  // })
  emit('close');
}
</script>