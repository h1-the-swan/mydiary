import React, { FC, useEffect, useState } from "react";
import { Layout, Menu } from "antd";
import "./App.css";
import {
  Link,
  Route,
  Routes,
  useLocation,
  useResolvedPath,
} from "react-router-dom";
import PocketArticles from "./routes/pocketArticles";
import GooglePhotos from "./routes/googlePhotos";
import SpotifyHistory from "./routes/spotifyHistory";
import Dogs from "./routes/dogs";
import DogAdd from "./routes/dogAdd";
import Recipes from "./routes/recipes";
import RecipeAdd from "./routes/recipeAdd";
import TestJoplin from "./routes/testJoplin";
import { PerformSongs, PerformSongAddOrCreate } from "./routes/performSongs";

const { Header, Content, Footer, Sider } = Layout;

// function App() {
//   return (
//     <div className="App">
//       <header className="App-header">
//         <img src={logo} className="App-logo" alt="logo" />
//         <p>
//           Edit <code>src/App.tsx</code> and save to reload.
//         </p>
//         <a
//           className="App-link"
//           href="https://reactjs.org"
//           target="_blank"
//           rel="noopener noreferrer"
//         >
//           Learn React
//         </a>
//       </header>
//     </div>
//   );
// }

// const Tags = () => {
//   const { data: tags, isLoading } = useReadTags(
//     {},
//     { query: { select: (d) => d.data } }
//   );
//   if (!tags) return null;
//   const items = tags.map((tag) => (
//     <p>
//       {tag.id} | {tag.is_pocket_tag} | {tag.name}
//     </p>
//   ));
//   return <div>{items}</div>;
// };

interface IRoute {
  path: string;
  title: string;
  element: JSX.Element;
}

const ROUTES: IRoute[] = [
  {
    path: "/pocket/articles",
    title: "Pocket Articles",
    element: <PocketArticles />,
  },
  {
    path: "/googlephotos/thumbnail",
    title: "Google Photos",
    element: <GooglePhotos />,
  },
  {
    path: "/spotify/history",
    title: "Spotify History",
    element: <SpotifyHistory />,
  },
  {
    path: "/dogs",
    title: "Dogs",
    element: <Dogs />,
  },
  {
    path: "/dogs/add",
    title: "Add Dog",
    element: <DogAdd />,
  },
  {
    path: "/recipes",
    title: "Recipes",
    element: <Recipes />,
  },
  {
    path: "/recipes/add",
    title: "Add Recipe",
    element: <RecipeAdd />,
  },
  {
    path: "/performSongs",
    title: "performSongs",
    element: <PerformSongs />,
  },
  {
    path: "/performSongs/song",
    title: "Add or Update performSong",
    element: <PerformSongAddOrCreate />,
  },
  {
    path: "/testJoplin",
    title: "testJoplin",
    element: <TestJoplin />,
  },
];

const App: FC = (props) => {
  const location = useLocation();
  const resolvedPath = useResolvedPath(location.pathname);
  console.log(location);
  console.log(resolvedPath);
  // const [currentPage, setCurrentPage] = useState<string>();
  return (
    <Layout>
      <Sider
        breakpoint="lg"
        collapsedWidth="0"
        onBreakpoint={(broken) => {
          console.log(broken);
        }}
        onCollapse={(collapsed, type) => {
          console.log(collapsed, type);
        }}
      >
        <div className="logo" />
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[resolvedPath.pathname]}
        >
          {ROUTES.map((r) => (
            <Menu.Item key={r.path}>
              <Link to={r.path}>{r.title}</Link>
            </Menu.Item>
          ))}
        </Menu>
      </Sider>
      <Layout>
        <Header
          className="site-layout-sub-header-background"
          style={{ padding: 0 }}
        />
        <Content style={{ margin: "24px 16px 0" }}>
          <div
            className="site-layout-background"
            style={{ padding: 24, minHeight: 360 }}
          >
            <Routes>
              {ROUTES.map((r) => (
                <Route path={r.path} element={r.element}></Route>
              ))}
            </Routes>
          </div>
        </Content>
        <Footer style={{ textAlign: "center" }}>Jason mydiary</Footer>
      </Layout>
    </Layout>
  );
};

export default App;
