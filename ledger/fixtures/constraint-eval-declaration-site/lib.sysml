library package Lib {
    private import ScalarValues::*;
    private import Connections::BinaryConnection;
    private import Objects::BinaryLinkObject;
    part def Foo { attribute controlled : Boolean default true; }
    connection def Link :> BinaryConnection {
        end source : Foo :>> BinaryLinkObject::source;
        end target : Foo :>> BinaryLinkObject::target;
        assert constraint { source.controlled and target.controlled }
    }
}
