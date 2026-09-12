package svt;

import org.omg.sysml.interactive.SysMLInteractive;
import org.omg.sysml.interactive.SysMLInteractiveResult;
import org.eclipse.xtext.validation.Issue;

import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;

/**
 * Tiny headless glue over the Pilot Implementation's SysMLInteractive engine
 * (org.omg.sysml.interactive) -- no Eclipse Workbench, no Jupyter protocol.
 *
 * Usage: java -jar pilot-glue.jar <file1.sysml> [file2.sysml ...]
 * Env:   SYSML_LIBRARY_DIR - path to a sysml.library directory (the Pilot
 *        repo's own sysml.library/, or an equivalent OMG standard library
 *        checkout). Required for any input that imports the standard
 *        library (ScalarValues, Connections, etc).
 *
 * Files are processed in order, each as its own resource added to the
 * running index (SysMLInteractive.process(content, true)) -- so a later
 * file resolves names declared in an earlier one, matching how a real
 * multi-file SysML v2 model is actually checked. Prints "CLEAN" and exits 0
 * if no file has an error-severity issue; otherwise prints every issue
 * found (across all files) and exits 1. This plain text is captured
 * verbatim by adapters/pilot_implementation.py as the RawResult.
 */
public class Main {
    public static void main(String[] args) throws Exception {
        if (args.length == 0) {
            System.err.println("usage: java -jar pilot-glue.jar <file1.sysml> [file2.sysml ...]");
            System.exit(2);
        }

        SysMLInteractive instance = SysMLInteractive.createInstance();
        String libraryDir = System.getenv("SYSML_LIBRARY_DIR");
        if (libraryDir != null && !libraryDir.isEmpty()) {
            instance.loadLibrary(libraryDir);
        }

        boolean anyErrors = false;
        List<String> lines = new ArrayList<>();
        for (String path : args) {
            String content = new String(Files.readAllBytes(Paths.get(path)));
            SysMLInteractiveResult result = instance.process(content, true);
            if (result.getException() != null) {
                anyErrors = true;
                lines.add(path + ": EXCEPTION: " + result.getException());
                continue;
            }
            if (result.hasErrors()) {
                anyErrors = true;
            }
            for (Issue issue : result.getIssues()) {
                lines.add(path + ": " + issue.getSeverity() + ": " + issue.getMessage()
                        + " (line " + issue.getLineNumber() + ")");
            }
        }

        System.out.println(anyErrors ? "ERRORS:" : "CLEAN");
        for (String line : lines) {
            System.out.println(line);
        }
        System.exit(anyErrors ? 1 : 0);
    }
}
