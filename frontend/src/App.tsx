import React, { FC } from "react";
import { Layout, Menu } from "antd";
import "./App.css";
import { Link, Route, Routes, useLocation, useResolvedPath } from "react-router-dom";
import PocketArticles from "./routes/pocketArticles";
import GooglePhotos from "./routes/googlePhotos";

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

const App: FC = (props) => {
  const location = useLocation();
  const resolvedPath = useResolvedPath(location.pathname);
  console.log(location);
  console.log(resolvedPath);
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
        <Menu theme="dark" mode="inline" defaultSelectedKeys={["1"]}>
          <Menu.Item key="1">
            <Link to={"/pocket/articles"}>Pocket Articles</Link>
          </Menu.Item>
          <Menu.Item key="2">
            <Link to={"/googlephotos/thumbnail"}>Google Photos</Link>
          </Menu.Item>
          <Menu.Item key="3">nav 3</Menu.Item>
          <Menu.Item key="4">nav 4</Menu.Item>
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
              <Route
                path="/pocket/articles"
                element={<PocketArticles />}
              ></Route>
              <Route path="/googlephotos/thumbnail" element={<GooglePhotos />}>
              </Route>
            </Routes>
          </div>
        </Content>
        <Footer style={{ textAlign: "center" }}>Jason mydiary</Footer>
      </Layout>
    </Layout>
  );
};

export default App;
