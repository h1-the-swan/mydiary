<template>
  <v-data-table :headers="headers" :items="items" :sort-by="[{ key: 'name', order: 'asc' }]" :search="search"
    class="elevation-1">
    <template v-slot:top>
      <v-toolbar flat>
        <v-toolbar-title>My CRUD</v-toolbar-title>
        <v-divider class="mx-4" inset vertical></v-divider>
        <v-spacer></v-spacer>
        <v-text-field v-model="search" append-icon="mdi-magnify" label="Search" single-line hide-details></v-text-field>
        <data-table-modal v-model:dialog="dialog" v-model:edited-index="editedIndex" v-model:edited-item="editedItem"
          @save="onSave" @close="onClose" />
        <v-btn color="primary" dark class="mb-2" @click="dialog = true">
          New Item
        </v-btn>
        <v-dialog v-model="dialogDelete" max-width="500px">
          <v-card>
            <v-card-title class="text-h5">Are you sure you want to delete this item?</v-card-title>
            <v-card-actions>
              <v-spacer></v-spacer>
              <v-btn color="blue-darken-1" variant="text" @click="closeDelete">Cancel</v-btn>
              <v-btn color="blue-darken-1" variant="text" @click="deleteItemConfirm">OK</v-btn>
              <v-spacer></v-spacer>
            </v-card-actions>
          </v-card>
        </v-dialog>
      </v-toolbar>
    </template>
    <template v-slot:[`item.actions`]="{ item }">
      <v-icon size="small" class="me-2" @click="editItem(item.raw)">
        mdi-pencil
      </v-icon>
      <v-icon size="small" @click="deleteItem(item.raw)">
        mdi-delete
      </v-icon>
    </template>
  </v-data-table>
</template>

<script lang="ts" setup>
import { computed, nextTick, ref, watch } from 'vue'
import DataTableModal from './DataTableModal.vue';
import { VoidTypeAnnotation } from '@babel/types';

const search = ref('');
const dialog = ref(false);
const dialogDelete = ref(false);
interface IHeader {
  key: string;
  title: string;
  align?: 'start' | 'end' | 'center';
  sortable?: boolean;
}

interface IProps {
  headers: IHeader[];
  items: any[];
  onSave(): void;

}
const props = defineProps<IProps>();

const headers = [...props.headers, { title: 'Actions', key: 'actions', sortable: false }];
interface IDessert {
  name: string;
  calories: number;
  fat: number;
  carbs: number;
  protein: number;
}
const desserts = ref<IDessert[]>([])
const editedIndex = ref(-1)
const editedItem = ref({
  name: '',
  calories: 0,
  fat: 0,
  carbs: 0,
  protein: 0,
})
const defaultItem = ref({
  name: '',
  calories: 0,
  fat: 0,
  carbs: 0,
  protein: 0,
})
function editItem(item: IDessert) {
  editedIndex.value = desserts.value.indexOf(item)
  editedItem.value = Object.assign({}, item)
  dialog.value = true
}
function deleteItem(item: IDessert) {
  editedIndex.value = desserts.value.indexOf(item)
  editedItem.value = Object.assign({}, item)
  dialogDelete.value = true
}
function deleteItemConfirm() {
  desserts.value.splice(editedIndex.value, 1)
  closeDelete()
}
function closeDelete() {
  dialogDelete.value = false
  nextTick(() => {
    editedItem.value = Object.assign({}, defaultItem.value)
    editedIndex.value = -1
  })
}
function onClose() {
  nextTick(() => {
    editedItem.value = Object.assign({}, defaultItem.value)
    editedIndex.value = -1
  })
}
watch(dialog, val => {
  val || close()
})
watch(dialogDelete, val => {
  val || closeDelete()
})
</script>