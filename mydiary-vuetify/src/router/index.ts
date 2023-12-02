// Composables
import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    component: () => import('@/layouts/default/Default.vue'),
    children: [
      {
        path: '',
        name: 'Home',
        // route level code-splitting
        // this generates a separate chunk (about.[hash].js) for this route
        // which is lazy-loaded when the route is visited.
        component: () => import(/* webpackChunkName: "home" */ '@/views/Home.vue'),
      },
      {
        path: '/test',
        name: 'Test',
        component: () => import(/* webpackChunkName: "test" */ '@/views/Test.vue'),
      },
      {
        path: '/performSongs',
        name: 'performSongs',
        component: () => import(/* webpackChunkName: "performsong" */ '@/views/PerformSongs.vue'),
      },
      {
        path: '/performSongs/new',
        name: 'new performSong',
        component: () => import(/* webpackChunkName: "performsong" */ '@/views/PerformSongNew.vue'),
      },
      {
        path: '/performSongs/:id',
        name: 'performSong',
        component: () => import(/* webpackChunkName: "performsong" */ '@/views/PerformSongs.vue'),
        props: true,
      },
      {
        path: '/pocket',
        name: 'pocket',
        component: () => import(/* webpackChunkName: "pocket" */ '@/views/Pocket.vue'),
        props: true,
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(process.env.BASE_URL),
  routes,
})

export default router
